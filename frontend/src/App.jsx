import { useEffect, useState } from 'react'

const wait = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

function App() {
  const [mode, setMode] = useState('challenge')
  const [configuration, setConfiguration] = useState(null)
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
        const configResponse = await fetch('/api/configuration', {
          cache: 'no-store',
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
        })
        if (!configResponse.ok) throw new Error('Could not load execution settings.')
        const config = await configResponse.json()

        if (active) {
          setConfiguration(config)
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
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const response = await fetch(`/api/submissions/${id}`, {
        cache: 'no-store',
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

      await wait(2000)
    }

    setMessage(
      'Stopped checking automatically. The submission may still ' +
      'be processing. Use Check result to look again.'
    )
  }

  async function submitCode() {
    if (isSubmitting || !configuration || (isChallenge && !problem)) return

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
          setMessage(typeof data.detail === 'string' ? data.detail : 'Submission failed. Check your code and input.')
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
          : 'Could not confirm submission. Wait and check the service before submitting again.'
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

  const outcome = result?.verdict ?? result?.status
  const labels = {
    accepted: 'Accepted', completed: 'Completed', wrong_answer: 'Wrong answer',
    runtime_error: 'Runtime error', timed_out: 'Time limit exceeded',
    output_limit: 'Output limit exceeded', runner_error: 'Execution unavailable',
    runner_timeout: 'Runner timed out', killed: 'Process stopped',
    received: 'Queued', running: 'Running',
  }
  const resultLabel = labels[outcome] ?? outcome ?? 'Ready to run'
  const resultTone = ['accepted', 'completed'].includes(outcome)
    ? 'success'
    : ['received', 'running'].includes(outcome) || (!outcome && isSubmitting)
      ? 'pending'
      : outcome ? 'failure' : 'idle'

  return (
    <div className="forge-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="CodeForge home">
          <span className="brand-symbol" aria-hidden="true">{'</>'}</span>
          <span>Code<span className="brand-light">Forge</span></span>
        </a>

        <nav className="mode-switch" aria-label="Execution mode">
          <button type="button" aria-pressed={isChallenge}
            disabled={isSubmitting} onClick={() => changeMode('challenge')}>
            Challenges
          </button>
          <button type="button" aria-pressed={!isChallenge}
            disabled={isSubmitting} onClick={() => changeMode('playground')}>
            Python Playground
          </button>
        </nav>

        <span className="environment-label">{configuration?.runtime_label ?? 'Python'} <span aria-hidden="true">/</span> {configuration?.cloud ? 'Cloud demo' : 'Local workspace'}</span>
      </header>

      <main className="workspace-main">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">{isChallenge ? 'Practice / Python' : 'Explore / Python'}</p>
            <h1>{isChallenge ? (problem?.title ?? 'Coding challenge') : 'Python Playground'}</h1>
            <p className="subtitle">{isChallenge
              ? 'Understand the problem. Write your solution. Put it to the test.'
              : 'A space to experiment, work through an idea, and see what happens.'}</p>
          </div>
          <div className="limits" aria-label="Execution limits">
            <span>5s per run</span><span>{configuration?.memory_label ?? 'Loading limits…'}</span>
          </div>
        </div>

        <div className="workspace-grid">
          <aside className="panel briefing">
            <div className="panel-bar">
              <h2>{isChallenge ? 'Problem' : 'Run settings'}</h2>
              <span className="subtle-label">{isChallenge ? 'Description' : 'Standard input'}</span>
            </div>
            <div className="briefing-body">
              {isChallenge ? (
                problemError ? <p className="error-notice" role="alert">{problemError}</p>
                : !problem ? <p role="status">Loading problem…</p>
                : <>
                    <p className="problem-description">{problem.description}</p>
                    <h3>Input format</h3><p>{problem.input_format}</p>
                    <h3>Output format</h3><p>{problem.output_format}</p>
                    <div className="example-card">
                      <div className="example-title">Example</div>
                      <div className="example-half"><span>Input</span><pre>{problem.example_input}</pre></div>
                      <div className="example-half"><span>Expected output</span><pre>{problem.example_output}</pre></div>
                    </div>
                    <div className="help-note"><span className="note-mark" aria-hidden="true">i</span>
                      <p>Your solution runs against the problem’s test cases. Print only the requested answer.</p>
                    </div>
                  </>
              ) : <>
                <label className="input-title" htmlFor="stdin">Standard input <span>Optional</span></label>
                <p className="input-help">If your program uses <code>input()</code>, enter the values here before running.</p>
                <textarea id="stdin" rows={7} value={stdin}
                  onChange={(event) => setStdin(event.target.value)}
                  spellCheck={false} disabled={isSubmitting}
                  placeholder={'Sam\nOne input per line'} />
                <p className="field-hint">One line for each input() call.</p>
                <div className="help-note"><span className="note-mark" aria-hidden="true">i</span>
                  <p>Input is supplied before execution. This is not an interactive terminal.</p>
                </div>
                <div className="run-notes">
                  <h3>Execution limits</h3>
                  <dl><div><dt>Time</dt><dd>5 seconds</dd></div><div><dt>Output</dt><dd>16 KiB</dd></div>
                    <div><dt>Network</dt><dd>Disabled</dd></div></dl>
                </div>
              </>}
            </div>
          </aside>

          <div className="execution-column">
            <section className="panel editor-panel" aria-label="Python editor">
              <div className="panel-bar editor-bar">
                <label className="file-label" htmlFor="code"><span className="file-icon" aria-hidden="true">Py</span>solution.py</label>
                <span className="language-label">{configuration?.runtime_label ?? 'Python'}</span>
              </div>
              <textarea id="code" rows={14} value={code}
                onChange={(event) => updateCode(event.target.value)} spellCheck={false}
                autoCapitalize="off" autoComplete="off"
                disabled={isSubmitting || (isChallenge && !problem)}
                aria-label="Python code" placeholder="# Write your Python code here" />
              {configuration?.cloud && (
                <p className="public-demo-note">Public demo · Shared limit: 100 submissions per 24 hours, two submissions per 10 seconds.</p>
              )}
              <div className="editor-actions">
                <span className="character-count">{code.length.toLocaleString()} characters</span>
                <button className="run-button" type="button" onClick={submitCode}
                  disabled={isSubmitting || !configuration || code.trim().length === 0 || (isChallenge && !problem)}>
                  <span aria-hidden="true">{isSubmitting ? '◌' : '▶'}</span>
                  {isSubmitting ? 'Processing…' : isChallenge ? 'Submit solution' : 'Run code'}
                </button>
              </div>
            </section>

            <section className="panel result-panel" aria-label="Submission result" aria-busy={isSubmitting}>
              <div className="panel-bar">
                <h2>{isChallenge ? 'Test results' : 'Output'}</h2>
                <div className="result-toolbar">
                  {submissionId && <button className="text-button" type="button" onClick={refreshResult} disabled={isSubmitting}>Check result</button>}
                  <span className={`status-pill ${resultTone}`}>{!outcome && isSubmitting ? 'Submitting' : resultLabel}</span>
                </div>
              </div>

              <div className="result-body">
                {!result && !message ? (
                  <div className="empty-result"><span aria-hidden="true" className="terminal-mark">{'>_'}</span>
                    <div><h3>{isChallenge ? 'Ready when you are' : 'Your output will appear here'}</h3>
                    <p>{isChallenge ? 'Submit your solution to see its verdict and test count.' : 'Run your code to see printed output, errors, and the exit code.'}</p></div>
                  </div>
                ) : <>
                  {message && <p className="processing-message" role="status">{message}</p>}
                  {result && (result.problem_id ? <>
                    <div className="verdict-summary"><strong className={resultTone}>{resultLabel}</strong>
                      <span><b>{result.tests_passed ?? '—'}</b> / {result.tests_total ?? '—'} tests passed</span>
                    </div>
                    <p className="field-hint">Execution status: {labels[result.status] ?? result.status}</p>
                  </> : <>
                    <div className="output-meta"><span>Output and errors</span><span>Exit code <b>{result.exit_code ?? '—'}</b></span></div>
                    <pre className="program-output">{result.output === null ? 'No output available yet.' : result.output === '' ? '(No output)' : result.output}</pre>
                  </>)}
                </>}
                {submissionId && <details className="submission-details"><summary>Submission details</summary><code>{submissionId}</code></details>}
              </div>
            </section>
          </div>
        </div>
        <footer className="workspace-footer"><span>CodeForge · Python execution workspace</span><span>{configuration?.cloud ? 'Cloud demo · Limited daily runs' : 'Local development build'}</span></footer>
      </main>
    </div>
  )
}

export default App
