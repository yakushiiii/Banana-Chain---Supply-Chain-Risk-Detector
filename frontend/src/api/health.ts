// Agreed /health response shape. Once the API serves /health with a response_model,
// replace this with the generated type: components["schemas"]["HealthResponse"].
export type HealthResponse = {
  api: 'ok' | 'error'
  db: 'ok' | 'error'
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch('/health')
  if (!res.ok) throw new Error(`/health returned ${res.status}`)
  return res.json()
}
