# CodeForge cloud deployment

These files add the hosted execution path. They do not deploy anything by
themselves. Git commands and Vercel configuration are performed by the owner.

## Architecture

The hosted frontend forwards `/api/*` to the FastAPI Vercel project. The API
stores submissions in Neon, then publishes only their IDs to Vercel Queues.
Vercel discovers `cloud_worker.handle_submission` through `pyproject.toml` and
generates a private subscriber function. It executes programs in fresh Vercel
Sandboxes and stores results in Neon. The frontend polls for results.

Local development still uses Redis, `worker.py`, Docker, and the local database.
The cloud path is selected when Vercel sets `VERCEL`. Do not manually enable
that variable for ordinary local development.

## Before deploying

1. Run `add_cloud_columns.sql` in the Neon SQL Editor, on the database/branch
   used by `code-forge-api`. It adds a nullable timestamp and an index without
   deleting existing submissions.
2. Keep `DATABASE_URL` configured on the backend. The public demo no longer
   requires `DEMO_ACCESS_CODE`; the old variable can be removed or left unused.
3. Copy the reviewed replacement files. Install the updated requirements.
   `check_cloud_integration.py` runs offline and does not spend cloud allowance.
4. Run frontend lint and build, inspect changed files, then commit and push.
   The owner performs all Git commands.
5. Confirm that the backend deployment lists the private queue subscriber and
   allows a **300-second** function duration. `vercel.json` requests this.
   If the build does not discover `cloud_worker`, stop and inspect the build log.
6. Wait for both deployments to become Ready before testing the hosted frontend.

Authentication uses Vercel's managed production OIDC token for SDK calls. Do
not copy the temporary local `VERCEL_OIDC_TOKEN` into production environment
variables. No Redis service is needed for the hosted path.

## Demo access and limits

Problem descriptions, submissions, and result retrieval are public. There is
no access-code field or authorization header requirement. Anyone with a
submission ID can retrieve its output; do not submit private information.
There are no user accounts or private submission ownership.

Admission is limited globally to 100 saved submissions in a rolling 24 hours
with a shared limit of two submissions per rolling 10 seconds, including failed submissions. A PostgreSQL transaction
lock serializes quota checks with insertion. A challenge can start up to five
sandboxes; execution stops at its first failed test. These application limits
reduce usage but are not a guarantee of remaining platform quota.

Each program has a five-second deadline, 16 KiB combined captured output,
16 KiB input, disabled networking, and an unprivileged user. The cloud child
has a 128 MiB address-space limit; its sandbox VM has a separate 2 GiB memory
allocation. This differs from the local Docker memory limit. Cloud filesystems
are writable and temporary. No application credentials are passed into the
submitted process. These controls are a prototype, not a security certification.

The default sandbox image ran Python 3.14.4 in the owner's seven-case check.
The interface says `Python (cloud)` because the provider's default image may
change. Local Docker still uses `python:3.13-slim`.

## Delivery and interruption behavior

Delivery is at least once. PostgreSQL serializes claiming a row. Terminal rows
are skipped on duplicate delivery. A delivery seeing an active run defers
instead of executing it twice. After six minutes, an interrupted running job
becomes `runner_error`; it is not automatically executed again. The configured
function limit is five minutes and individual sandbox lifetimes are 30 seconds.

Database errors escape the subscriber so Vercel can retry delivery. Execution
or cleanup errors become `runner_error`. If delivery exhausts all three attempts
or the queue service is unavailable throughout, manual investigation is still
needed; this prototype does not have a dead-letter dashboard.

Saving to the database and sending to the queue are separate operations. If
delivery cannot be confirmed, the API returns 503 with the saved submission ID.
Check that ID before deciding on recovery. There is no transactional outbox.
Do not run the local Redis recovery script against hosted submissions.

## Hosted acceptance checks after deployment

1. Confirm the page shows no access-code field. An unauthenticated submission
   must be accepted when quota remains; quota exhaustion must still return 429.
2. Playground: `name = input(); print("Hello,", name)` with `Sam` as input
   produces `Hello, Sam` and exit code 0.
3. Challenge: sum two integers; expect `accepted`, 5/5.
4. Challenge: `print(999)`; expect `wrong_answer`.
5. Confirm runtime error, time limit and output limit results as allowance permits.

Allow at least two submissions per 10 seconds. Inspect the backend queue
and function logs if a submission stays received. Redact tokens and submitted
private code before sharing logs.

## Validation status

The owner reports all seven cloud-runner checks passed with sandbox cleanup.
The integration's offline handler/worker tests cover public access and quotas with mocked database
and queue calls; they are not live PostgreSQL concurrency or hosted delivery
tests. The Windows sandbox prevents asyncio's loopback socket, so tests call
registered route handlers/dependencies directly rather than opening HTTP.
Deployment and hosted acceptance checks remain outstanding.
