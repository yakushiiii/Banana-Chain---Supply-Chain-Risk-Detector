// Cross-platform OpenAPI type generation (Windows PowerShell, macOS, Linux).
// Uses the project's openapi-typescript dev dependency; run `npm install` first.
import { writeFile } from 'node:fs/promises'
import openapiTS, { astToString } from 'openapi-typescript'

const base = process.env.API_URL ?? 'http://127.0.0.1:5000'
const specUrl = base.endsWith('/openapi.json')
  ? base
  : new URL('openapi.json', base.endsWith('/') ? base : `${base}/`).toString()

const response = await fetch(specUrl)
if (!response.ok) throw new Error(`OpenAPI request failed: ${response.status} ${specUrl}`)
const document = await response.json()
const content = astToString(await openapiTS(document))
await writeFile(new URL('../src/api/schema.d.ts', import.meta.url), content, 'utf8')
console.log(`Generated src/api/schema.d.ts from ${specUrl}`)
