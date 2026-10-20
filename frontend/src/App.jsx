import { useEffect, useState } from 'react'

const wait = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

function App() {
  const [problem, setProblem] = useState(null)
  const [problemError, setProblemError] = useState('')
  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionId, setSubmissionId] = useState(null)
  const [result, setResult] = useState(null)

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
          throw new Error(`Problem request failed: ${response.status}`)
        }

        const data = await response.json()

        if (active) {
          setProblem(data)
          setCode(data.starter_code)
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
        setMessage('Judging finished.')
        return
      }

      setMessage(
        data.status === 'received'
          ? 'Waiting for the worker...'
          : 'Running test cases...'
      )

      await wait(1000)
    }

    setMessage(
      'Stopped checking automatically. Your submission may still ' +
      'be processing. Use Check result to look again.'
    )
  }

  async function submitSolution() {
    if (!problem || isSubmitting) return

    setIsSubmitting(true)
    setSubmissionId(null)
    setResult(null)
    setMessage('Sending your solution...')

    let savedId = null

    try {
      const response = await fetch('/api/submissions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          problem_id: problem.id,
          code: code,
        }),
        signal: AbortSignal.timeout(10000),
      })

      const data = await response.json()

      if (!response.ok) {
        savedId = data.detail?.id

        if (savedId) {
          setSubmissionId(savedId)
          setMessage(
            'Submission saved, but queue delivery was not confirmed. ' +
            'Use Check result before deciding whether recovery is needed.'
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
          ? 'Submission saved, but checking its result failed. ' +
            'Use Check result to try again.'
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

  if (problemError) {
    return (
      <main>
        <h1>CodeForge</h1>
        <p role="alert">{problemError}</p>
      </main>
    )
  }

  if (!problem) {
    return (
      <main>
        <h1>CodeForge</h1>
        <p role="status">Loading problem...</p>
      </main>
    )
  }

  return (
    <main>
      <h1>CodeForge</h1>

      <section aria-label="Problem description">
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
      </section>

      <label htmlFor="code">Python solution</label>

      <div>
        <textarea
          id="code"
          rows={10}
          cols={50}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          spellCheck={false}
          disabled={isSubmitting}
        />
      </div>

      <button
        type="button"
        onClick={submitSolution}
        disabled={isSubmitting || code.trim().length === 0}
      >
        {isSubmitting ? 'Working...' : 'Submit solution'}
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
          <p>Verdict: {result.verdict ?? 'Pending'}</p>
          <p>
            Tests passed: {result.tests_passed ?? '—'}
            {' / '}
            {result.tests_total ?? '—'}
          </p>
        </section>
      )}
    </main>
  )
}

export default App