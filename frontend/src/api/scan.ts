export type ComponentRow = {
  name: string
  version: string | null
  type: string
  purl: string | null
  vuln_count: number | null // null = not checked
  severity: string // Critical | High | Medium | Low | Unknown | None | Not checked
  rank: number // higher = worse, used for sorting
}

/** The complete CycloneDX document returned by Syft. */
export type CycloneDxBom = {
  bomFormat: 'CycloneDX'
  specVersion: string
  [field: string]: unknown
}

export type ScanResult = {
  component_count: number
  vulns_ok: boolean
  components: ComponentRow[]
  sbom: CycloneDxBom
}

/** Download the original SBOM instead of reconstructing it from result rows. */
export function downloadSbom(sbom: CycloneDxBom): void {
  const blob = new Blob([JSON.stringify(sbom, null, 2)], {
    type: 'application/vnd.cyclonedx+json',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'bom.cdx.json'
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Allow the browser to start the download before releasing the object URL.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
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