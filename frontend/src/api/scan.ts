export type ComponentRow = {
  name: string
  version: string | null
  type: string
  purl: string | null
  vuln_count: number | null // null = not checked
  severity: string // Critical | High | Medium | Low | Unknown | None | Not checked
  rank: number // higher = worse, used for sorting
}

export type ScanResult = {
  component_count: number
  vulns_ok: boolean
  components: ComponentRow[]
}

export async function scanRepo(
  input: { url: string } | { files: FileList },
): Promise<ScanResult> {
  const form = new FormData()
  if ('url' in input) {
    form.append('url', input.url)
  } else {
    Array.from(input.files).forEach((f) => form.append('files', f))
  }

  const res = await fetch('/api/scan', { method: 'POST', body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Scan failed (${res.status})`)
  }
  return res.json()
}