export type ComponentRow = {
  name: string
  version: string | null
  type: string
  purl: string | null
  vuln_count: number | null
  severity: string
  rank: number
}

export type ScanResult = {
  scan_id?: string
  component_count: number
  vulns_ok: boolean
  components: ComponentRow[]
}

export type ScanSubmission = {
  scan_id: string
  task_id: string
  status: 'queued'
}

export type ScanStatus = {
  task_id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  phase?: string
  result?: ScanResult
  error?: string
}

export async function scanRepo(
  input: { url: string } | { files: FileList },
): Promise<ScanSubmission> {
  const form = new FormData()

  if ('url' in input) {
    form.append('url', input.url)
  } else {
    Array.from(input.files).forEach((f) => {
      form.append('files', f)
    })
  }

  const res = await fetch('/api/scan', {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => null)

    throw new Error(
      body?.detail ?? `Scan failed (${res.status})`,
    )
  }

  return res.json()
}

export async function getScanStatus(
  taskId: string,
): Promise<ScanStatus> {
  const res = await fetch(
    `/api/scan/${encodeURIComponent(taskId)}`,
  )

  if (!res.ok) {
    const body = await res.json().catch(() => null)

    throw new Error(
      body?.detail ??
        `Could not get scan status (${res.status})`,
    )
  }

  return res.json()
}