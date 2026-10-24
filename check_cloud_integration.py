"""Offline API/queue regression checks. Never connects to a database or sandbox."""
import asyncio
import importlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
fake_database = ModuleType('database')
fake_database.get_connection = MagicMock(side_effect=AssertionError('Unexpected database connection'))
sys.modules['database'] = fake_database

import main
import cloud_worker
from cloud_settings import require_demo_access
from fastapi import HTTPException
from vercel.queue import RetryAfter
from vercel.queue import sync as queue_sync

SECRET = 'test-only-access-code-not-a-real-secret'


def request(method, path, data=None, token=None):
    # Exercise handlers and their registered access dependency directly. The
    # restricted Windows environment cannot create asyncio's loopback socket.
    from fastapi import Response
    from pydantic import ValidationError
    from uuid import UUID
    route_path = '/submissions/{submission_id}' if path.startswith('/submissions/') else path
    route = next(r for r in main.app.routes if r.path == route_path and method in r.methods)
    try:
        for dependency in route.dependant.dependencies:
            dependency.call('Bearer ' + token if token is not None else None)
        if method == 'POST':
            result = route.endpoint(main.SubmissionRequest(**data))
        elif path.startswith('/submissions/'):
            result = route.endpoint(UUID(path.rsplit('/', 1)[1]), Response())
        else:
            result = route.endpoint()
        return 200, result
    except HTTPException as error:
        return error.status_code, {'detail': error.detail}
    except ValidationError:
        return 422, {'detail': 'validation failed'}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'VERCEL': '1', 'DEMO_ACCESS_CODE': SECRET})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def connection(self, *records):
        connection = MagicMock()
        cursors = []
        for record in records:
            cursor = MagicMock()
            cursor.fetchone.return_value = record
            cursors.append(cursor)
        connection.execute.side_effect = cursors
        context = MagicMock()
        context.__enter__.return_value = connection
        return context, connection

    def test_configuration_is_public_and_accurate(self):
        status, data = request('GET', '/configuration')
        self.assertEqual(status, 200)
        self.assertTrue(data['requires_access_code'])
        self.assertEqual(data['memory_label'], '128 MiB address space')

    def test_unauthorized_post_never_saves_or_queues(self):
        with patch.object(main, 'get_connection') as db, patch.object(queue_sync, 'QueueClient') as queue:
            status, _ = request('POST', '/submissions', {'code': 'print(2)'})
        self.assertEqual(status, 401)
        db.assert_not_called()
        queue.assert_not_called()

    def test_missing_secret_fails_closed(self):
        with patch.dict(os.environ, {'DEMO_ACCESS_CODE': ''}):
            status, _ = request('POST', '/submissions', {'code': 'print(2)'}, SECRET)
        self.assertEqual(status, 503)

    def test_wrong_secret_protects_result(self):
        status, _ = request('GET', f'/submissions/{uuid4()}', token='wrong')
        self.assertEqual(status, 401)

    def test_local_mode_requires_no_secret(self):
        with patch.dict(os.environ, {'VERCEL': ''}):
            require_demo_access(None)
            status, data = request('GET', '/configuration')
        self.assertEqual(status, 200)
        self.assertFalse(data['requires_access_code'])

    def test_daily_cap_rejects_before_insert(self):
        context, connection = self.connection(None, {'daily': 10, 'recent': 0})
        with patch.object(main, 'get_connection', return_value=context), patch.object(queue_sync, 'QueueClient') as queue:
            status, _ = request('POST', '/submissions', {'code': 'print(2)'}, SECRET)
        self.assertEqual(status, 429)
        self.assertEqual(connection.execute.call_count, 2)
        queue.assert_not_called()

    def test_burst_cap_rejects(self):
        context, _ = self.connection(None, {'daily': 2, 'recent': 2})
        with patch.object(main, 'get_connection', return_value=context):
            status, _ = request('POST', '/submissions', {'code': 'print(2)'}, SECRET)
        self.assertEqual(status, 429)

    def test_cloud_publishes_only_id_after_commit(self):
        saved_id = str(uuid4())
        context, _ = self.connection(None, {'daily': 0, 'recent': 0}, {'id': saved_id, 'status': 'received'})
        events = []
        context.__exit__.side_effect = lambda *args: events.append('commit') or False
        with patch.object(main, 'get_connection', return_value=context), patch.object(queue_sync, 'QueueClient') as queue, patch.object(main, 'queue_client') as redis:
            queue.return_value.send.side_effect = lambda *args, **kwargs: events.append('publish')
            status, data = request('POST', '/submissions', {'code': 'print(2)'}, SECRET)
            args, kwargs = queue.return_value.send.call_args
        self.assertEqual(status, 200)
        self.assertEqual(events, ['commit', 'publish'])
        self.assertEqual(set(args[1]), {'submission_id'})
        self.assertEqual(kwargs['idempotency_key'], args[1]['submission_id'])
        redis.rpush.assert_not_called()

    def test_queue_failure_returns_saved_id(self):
        saved_id = str(uuid4())
        context, _ = self.connection(None, {'daily': 0, 'recent': 0}, {'id': saved_id, 'status': 'received'})
        with patch.object(main, 'get_connection', return_value=context), patch.object(queue_sync, 'QueueClient') as queue:
            queue.return_value.send.side_effect = RuntimeError('offline')
            status, data = request('POST', '/submissions', {'code': 'print(2)'}, SECRET)
        self.assertEqual(status, 503)
        self.assertIsNotNone(data['detail']['id'])

    def test_invalid_utf8_input_is_rejected(self):
        with patch.object(main, 'get_connection') as db:
            status, _ = request('POST', '/submissions', {'code': 'print(2)', 'stdin': '😀' * 5000}, SECRET)
        self.assertEqual(status, 422)
        db.assert_not_called()

    def test_challenge_custom_input_rejected(self):
        status, _ = request('POST', '/submissions', {'code': 'print(2)', 'problem_id': 'add-two-integers', 'stdin': '3 5'}, SECRET)
        self.assertEqual(status, 422)

    def record(self, status='received', stale=False):
        return {'id': uuid4(), 'code': 'print(2)', 'stdin': '', 'problem_id': None, 'status': status, 'stale': stale}

    def test_completed_duplicate_does_not_execute(self):
        context, _ = self.connection(self.record('completed'))
        with patch.object(cloud_worker, 'get_connection', return_value=context), patch.object(cloud_worker, 'execute') as execute:
            cloud_worker.process_cloud_submission(uuid4())
        execute.assert_not_called()

    def test_active_duplicate_is_deferred(self):
        context, _ = self.connection(self.record('running'))
        with patch.object(cloud_worker, 'get_connection', return_value=context), patch.object(cloud_worker, 'execute') as execute:
            with self.assertRaises(RetryAfter):
                cloud_worker.process_cloud_submission(uuid4())
        execute.assert_not_called()

    def test_interrupted_run_becomes_error_without_reexecution(self):
        context, _ = self.connection(self.record('running', stale=True))
        with patch.object(cloud_worker, 'get_connection', return_value=context), patch.object(cloud_worker, 'execute') as execute, patch.object(cloud_worker, 'save_result') as save:
            cloud_worker.process_cloud_submission(uuid4())
        execute.assert_not_called()
        self.assertEqual(save.call_args.args[1]['status'], 'runner_error')

    def test_execution_failure_is_persisted(self):
        context, _ = self.connection(self.record(), None)
        with patch.object(cloud_worker, 'get_connection', return_value=context), patch.object(cloud_worker, 'execute', side_effect=RuntimeError('setup failed')), patch.object(cloud_worker, 'save_result') as save:
            cloud_worker.process_cloud_submission(uuid4())
        self.assertEqual(save.call_args.args[1]['status'], 'runner_error')

    def test_database_failure_propagates_for_redelivery(self):
        context, _ = self.connection(self.record(), None)
        with patch.object(cloud_worker, 'get_connection', return_value=context), patch.object(cloud_worker, 'execute', return_value=cloud_worker.failure_result(None)), patch.object(cloud_worker, 'save_result', side_effect=RuntimeError('database offline')):
            with self.assertRaisesRegex(RuntimeError, 'database offline'):
                cloud_worker.process_cloud_submission(uuid4())

    def test_challenge_uses_all_five_cloud_cases(self):
        record = self.record()
        record['problem_id'] = 'add-two-integers'
        def runner(code, stdin):
            return {'status': 'completed', 'output': str(sum(map(int, stdin.split()))), 'exit_code': 0}
        with patch.object(cloud_worker, 'run_code_cloud', side_effect=runner) as run:
            result = cloud_worker.execute(record)
        self.assertEqual(result['verdict'], 'accepted')
        self.assertEqual(result['tests_passed'], 5)
        self.assertEqual(run.call_count, 5)

    def test_wrong_answer_stops_after_first_case(self):
        record = self.record()
        record['problem_id'] = 'add-two-integers'
        with patch.object(cloud_worker, 'run_code_cloud', return_value={'status': 'completed', 'output': '99', 'exit_code': 0}) as run:
            result = cloud_worker.execute(record)
        self.assertEqual(result['verdict'], 'wrong_answer')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(run.call_count, 1)

    def test_playground_result_includes_nullable_judging_fields(self):
        with patch.object(cloud_worker, 'run_code_cloud', return_value={'status': 'completed', 'output': '2\n', 'exit_code': 0}):
            result = cloud_worker.execute(self.record())
        self.assertIsNone(result['verdict'])
        self.assertEqual(result['output'], '2\n')

    def test_malformed_queue_message_never_executes(self):
        with patch.object(cloud_worker, 'process_cloud_submission') as process:
            coroutine = cloud_worker.handle_submission(SimpleNamespace(payload={'submission_id': 'not-a-uuid'}))
            with self.assertRaises(StopIteration):
                coroutine.send(None)
        process.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
