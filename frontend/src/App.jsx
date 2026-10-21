import { useEffect, useState } from 'react'

const wait = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

function App() {
  const [mode, setMode] = useState('challenge')
  const [problem, setProblem] = useState(null)
  const [problemError, setProblemError] = useState('')

  const [challengeCode, setChallengeCode] = useState('')
  const [playgroundCode, setPlaygroundCode] = useState(
    'name = input()\nprint("Hello,", name)'
  )
  const [stdin, setStdin] = useState('Sam\n')

  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionId, setSubmissionId] = useState(null)
  const [result, setResult] = useState(null)

  const isChallenge = mode === 'challenge'
  const code = isChallenge ? challengeCode : playgroundCode

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    async function loadProblem() {
      try {
        const response = await fetch(
          '/api/problems/add-two-integers',
          {
            signal: AbortSignal.any([
              controller.signal,
              AbortSignal.timeout(10000),
            ]),
          }
        )

        if (!response.ok) {
          throw new Error('Could not load the problem.')
        }

        const data = await response.json()

        if (active) {
          setProblem(data)
          setChallengeCode(data.starter_code)
        }
      } catch {
        if (active) {
          setProblemError(
            'Could not load the problem. Check that the API is ' +
            'running, then refresh this page.'
          )
        }
      }
    }

    loadProblem()

    return () => {
      active = false
      controller.abort()
    }
  }, [])

  function changeMode(nextMode) {
    if (isSubmitting || nextMode === mode) return

    setMode(nextMode)
    setMessage('')
    setSubmissionId(null)
    setResult(null)
  }

  function updateCode(value) {
    if (isChallenge) {
      setChallengeCode(value)
    } else {
      setPlaygroundCode(value)
    }
  }

  async function checkResult(id) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const response = await fetch(`/api/submissions/${id}`, {
        signal: AbortSignal.timeout(10000),
      })

      if (!response.ok) {
        throw new Error('Could not retrieve the submission.')
      }

      const data = await response.json()
      setResult(data)

      if (data.status !== 'received' && data.status !== 'running') {
        setMessage('Processing finished.')
        return
      }

      setMessage(
        data.status === 'received'
          ? 'Waiting for the worker...'
          : 'Executing...'
      )

      await wait(1000)
    }

    setMessage(
      'Stopped checking automatically. The submission may still ' +
      'be processing. Use Check result to look again.'
    )
  }

  async function submitCode() {
    if (isSubmitting || (isChallenge && !problem)) return

    setIsSubmitting(true)
    setSubmissionId(null)
    setResult(null)
    setMessage('Sending your code...')

    const payload = isChallenge
      ? { problem_id: problem.id, code: challengeCode }
      : { code: playgroundCode, stdin: stdin }

    let savedId = null

    try {
      const response = await fetch('/api/submissions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(10000),
      })

      const data = await response.json()

      if (!response.ok) {
        savedId = data.detail?.id

        if (savedId) {
          setSubmissionId(savedId)
          setMessage(
            'Submission saved, but queue delivery was not confirmed. ' +
            'Use Check result before attempting recovery.'
          )
        } else {
          setMessage(`Submission failed: ${JSON.stringify(data.detail)}`)
        }

        return
      }

      savedId = data.id
      setSubmissionId(savedId)
      await checkResult(savedId)
    } catch {
      setMessage(
        savedId
          ? 'Submission saved, but checking failed. Use Check result.'
          : 'Could not confirm submission. Check the API terminal ' +
            'before submitting again.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function refreshResult() {
    if (!submissionId || isSubmitting) return

    setIsSubmitting(true)
    setMessage('Checking result...')

    try {
      await checkResult(submissionId)
    } catch {
      setMessage('Could not check the result. Check that the API is running.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main>
      <h1>CodeForge</h1>
      <p>Solve challenges or run your own Python programs.</p>

      <nav aria-label="Execution mode">
        <button
          type="button"
          aria-pressed={isChallenge}
          disabled={isSubmitting}
          onClick={() => changeMode('challenge')}
        >
          Challenges
        </button>

        <button
          type="button"
          aria-pressed={!isChallenge}
          disabled={isSubmitting}
          onClick={() => changeMode('playground')}
        >
          Python Playground
        </button>
      </nav>

      {isChallenge ? (
        <section aria-label="Problem description">
          {problemError ? (
            <p role="alert">{problemError}</p>
          ) : !problem ? (
            <p role="status">Loading problem...</p>
          ) : (
            <>
              <h2>{problem.title}</h2>
              <p>{problem.description}</p>

              <h3>Input format</h3>
              <p>{problem.input_format}</p>

              <h3>Output format</h3>
              <p>{problem.output_format}</p>

              <h3>Example input</h3>
              <pre>{problem.example_input}</pre>

              <h3>Expected output</h3>
              <pre>{problem.example_output}</pre>
            </>
          )}
        </section>
      ) : (
        <section>
          <h2>Python Playground</h2>
          <p>
            Write Python code and run it. If it uses input(),
            enter the required lines in Standard input below.
          </p>
          <p>
            Each run has a five-second execution limit and a
            16 KiB output limit.
          </p>
        </section>
      )}

      <label htmlFor="code">Python code</label>

      <textarea
        id="code"
        rows={10}
        value={code}
        onChange={(event) => updateCode(event.target.value)}
        spellCheck={false}
        disabled={isSubmitting || (isChallenge && !problem)}
      />

      {!isChallenge && (
        <section>
          <label htmlFor="stdin">Standard input (optional)</label>
          <p>Provide input before running. This is not an interactive terminal.</p>

          <textarea
            id="stdin"
            rows={4}
            value={stdin}
            onChange={(event) => setStdin(event.target.value)}
            spellCheck={false}
            disabled={isSubmitting}
          />
        </section>
      )}

      <button
        type="button"
        onClick={submitCode}
        disabled={
          isSubmitting ||
          code.trim().length === 0 ||
          (isChallenge && !problem)
        }
      >
        {isSubmitting
          ? 'Working...'
          : isChallenge
            ? 'Submit solution'
            : 'Run code'}
      </button>

      {submissionId && (
        <button
          type="button"
          onClick={refreshResult}
          disabled={isSubmitting}
        >
          Check result
        </button>
      )}

      <p role="status">{message}</p>

      {submissionId && <p>Submission ID: {submissionId}</p>}

      {result && (
        <section aria-label="Submission result">
          <h2>Result</h2>
          <p>Status: {result.status}</p>

          {result.problem_id ? (
            <>
              <p>Verdict: {result.verdict ?? 'Pending'}</p>
              <p>
                Tests passed: {result.tests_passed ?? '—'}
                {' / '}
                {result.tests_total ?? '—'}
              </p>
            </>
          ) : (
            <>
              <p>Exit code: {result.exit_code ?? '—'}</p>
              <h3>Output and errors</h3>
              <pre>
                {result.output === null
                  ? 'No output available yet.'
                  : result.output === ''
                    ? '(No output)'
                    : result.output}
              </pre>
            </>
          )}
        </section>
      )}
    </main>
  )
}

export default App