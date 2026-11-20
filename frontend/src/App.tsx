import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResponse } from './api/health'
import { getScanStatus, scanRepo, type ScanResult } from './api/scan'
import ResultsTable from './ResultsTable'
import SecuritySummary from './SecuritySummary'

type Status = 'loading' | 'ok' | 'error'
type Tab = 'github' | 'upload'

const POLL_MS = 5000

function StatusBadge({ label, status }: { label: string; status: Status }) {
  const styles = {
    loading: 'bg-gray-100 text-gray-600 ring-gray-300',
    ok: 'bg-green-50 text-green-700 ring-green-600/30',
    error: 'bg-red-50 text-red-700 ring-red-600/30',
  }[status]
  const text = { loading: 'Checking…', ok: 'Healthy', error: 'Unreachable' }[status]

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3">
      <span className="font-medium text-gray-900">{label}</span>
      <span className={`rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset ${styles}`}>
        {text}
      </span>
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Scanner state
  const [activeTab, setActiveTab] = useState<Tab>('github')
  const [githubUrl, setGithubUrl] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [scannedTarget, setScannedTarget] = useState<string | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanStatus, setScanStatus] = useState<'queued' | 'running' | 'done' | 'failed' | null>(null)
  const [scanPhase, setScanPhase] = useState<string | null>(null)

  useEffect(() => {
    const check = () =>
      fetchHealth()
        .then((h) => {
          setHealth(h)
          setError(null)
        })
        .catch((e: Error) => {
          setHealth(null)
          setError(e.message)
        })

    check()
    const id = setInterval(check, POLL_MS)
    return () => clearInterval(id)
  }, [])

  const loading = !health && !error
  const apiStatus: Status = loading ? 'loading' : health?.api === 'ok' ? 'ok' : 'error'
  const dbStatus: Status = loading ? 'loading' : health?.db === 'ok' ? 'ok' : 'error'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setResult(null)
    setScanError(null)

    if (activeTab === 'github' && !githubUrl.trim()) {
      setScanError('Enter a GitHub URL.')
      return
    }
    if (activeTab === 'upload' && (!selectedFiles || selectedFiles.length === 0)) {
      setScanError('Choose at least one file.')
      return
    }

    setScanning(true)
    setScanStatus('queued')
    setScanPhase(null)
    const target = activeTab === 'github' ? githubUrl.trim() : `${selectedFiles?.length ?? 1} uploaded file(s)`
    try {
      const submission = await scanRepo(
        activeTab === 'github' ? { url: githubUrl.trim() } : { files: selectedFiles! },
      )
      setScannedTarget(target)

      let finished = false
      while (!finished) {
        const status = await getScanStatus(submission.task_id)
        setScanStatus(status.status)
        setScanPhase(status.phase ?? null)

        if (status.status === 'done' && status.result) {
          setResult(status.result)
          finished = true
        } else if (status.status === 'failed') {
          throw new Error(status.error ?? 'Scan failed.')
        } else {
          await new Promise((resolve) => setTimeout(resolve, POLL_MS))
        }
      }
    } catch (err) {
      setScanError((err as Error).message)
      setScanStatus('failed')
    } finally {
      setScanning(false)
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="mx-auto max-w-4xl space-y-8">
        <div>
          <h1 className="text-3xl font-extrabold text-gray-900">Banana Chain</h1>
          <p className="mt-1 text-gray-600">Software Supply Chain Risk & Vulnerability Detector</p>
        </div>

        {/* Scan / Upload Section */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-xs">
          <h2 className="text-lg font-semibold text-gray-900">Scan a Repository</h2>
          <p className="mt-1 text-sm text-gray-500">
            Provide a public GitHub link or upload project source files to generate an SBOM and detect risks.
          </p>

          {/* Mode Switcher Tabs */}
          <div className="mt-4 flex rounded-lg bg-gray-100 p-1">
            <button
              type="button"
              onClick={() => {
                setActiveTab('github')
                { setResult(null); setScanError(null); setScanStatus(null); setScanPhase(null) }
              }}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition-all ${
                activeTab === 'github'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              GitHub Link
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab('upload')
                { setResult(null); setScanError(null); setScanStatus(null); setScanPhase(null) }
              }}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition-all ${
                activeTab === 'upload'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Upload Repo / Files
            </button>
          </div>

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            {activeTab === 'github' ? (
              <div className="space-y-3">
                <label htmlFor="github-url" className="block text-sm font-medium text-gray-700">
                  GitHub Repository URL
                </label>
                <div className="flex gap-2">
                  <input
                    id="github-url"
                    type="url"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    placeholder="https://github.com/user/repository"
                    className="block w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => setGithubUrl('https://github.com/pallets/flask')}
                    className="shrink-0 rounded-lg border border-gray-300 bg-gray-50 px-3 py-2.5 text-xs font-medium text-gray-700 hover:bg-gray-100"
                  >
                    Paste Sample
                  </button>
                </div>
                <button
                  type="submit"
                  disabled={scanning}
                  className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-xs hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  {scanning ? 'Scanning…' : 'Analyze GitHub Repository'}
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <label htmlFor="repo-files" className="block text-sm font-medium text-gray-700">
                  Select Project Folder or Files
                </label>
                <div className="flex items-center justify-center rounded-lg border-2 border-dashed border-gray-300 px-6 py-6 text-center hover:border-gray-400">
                  <div className="space-y-1 text-center">
                    <svg
                      className="mx-auto h-9 w-9 text-gray-400"
                      stroke="currentColor"
                      fill="none"
                      viewBox="0 0 48 48"
                      aria-hidden="true"
                    >
                      <path
                        d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <div className="flex text-sm text-gray-600 justify-center">
                      <label
                        htmlFor="repo-files"
                        className="relative cursor-pointer font-medium text-indigo-600 hover:text-indigo-500"
                      >
                        <span>Choose files to upload</span>
                        <input
                          id="repo-files"
                          type="file"
                          multiple
                          className="sr-only"
                          onChange={(e) => setSelectedFiles(e.target.files)}
                        />
                      </label>
                    </div>
                    <p className="text-xs text-gray-500">
                      {selectedFiles && selectedFiles.length > 0
                        ? `${selectedFiles.length} file(s) selected`
                        : 'Select project files, archives, or lockfiles'}
                    </p>
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={scanning}
                  className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-xs hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  {scanning ? 'Scanning…' : 'Upload & Analyze Repo'}
                </button>
              </div>
            )}
          </form>

          {scanError && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {scanError}
            </div>
          )}

          {scanStatus && (
            <div className={`mt-4 rounded-lg border p-4 ${
              scanStatus === 'failed'
                ? 'border-red-200 bg-red-50'
                : scanStatus === 'done'
                  ? 'border-green-200 bg-green-50'
                  : 'border-indigo-100 bg-indigo-50'
            }`}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Scan status</p>
                  <p className="mt-0.5 text-xs text-gray-600">
                    {scanStatus === 'queued' && 'Waiting for a worker…'}
                    {scanStatus === 'running' && (scanPhase ? `${scanPhase.charAt(0).toUpperCase()}${scanPhase.slice(1)}…` : 'Processing…')}
                    {scanStatus === 'done' && 'Scan completed successfully.'}
                    {scanStatus === 'failed' && 'Scan failed.'}
                  </p>
                </div>
                <span className={`rounded-full bg-white px-3 py-1 text-xs font-semibold ring-1 ring-inset ${
                  scanStatus === 'failed'
                    ? 'text-red-700 ring-red-600/20'
                    : scanStatus === 'done'
                      ? 'text-green-700 ring-green-600/20'
                      : 'text-indigo-700 ring-indigo-600/20'
                }`}>
                  {scanStatus.charAt(0).toUpperCase() + scanStatus.slice(1)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Results Section */}
        {result && (
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-xs space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Scan Results</h2>
                {scannedTarget && (
                  <p className="mt-0.5 max-w-md truncate font-mono text-xs text-gray-500">
                    Target: {scannedTarget}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => {
                  setResult(null)
                  setScannedTarget(null)
                  setScanError(null)
                  setScanStatus(null)
                  setScanPhase(null)
                }}
                className="text-xs font-medium text-gray-500 underline hover:text-gray-700"
              >
                Clear Results
              </button>
            </div>

            {!result.vulns_ok && (
              <p className="rounded-md border border-yellow-200 bg-yellow-50 p-2.5 text-xs text-yellow-800">
                Could not reach the OSV database, so vulnerabilities were not checked.
              </p>
            )}

            <SecuritySummary components={result.components} vulnsOk={result.vulns_ok} />

            <ResultsTable components={result.components} />
          </div>
        )}

        {/* System Status Section */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-xs">
          <h2 className="text-base font-semibold text-gray-900">System Status</h2>
          <p className="mt-0.5 text-xs text-gray-500">Live monitoring of backend services</p>

          <div className="mt-4 space-y-3">
            <StatusBadge label="API" status={apiStatus} />
            <StatusBadge label="Database" status={dbStatus} />
          </div>

          {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
        </div>
      </div>
    </main>
  )
}