import { useMemo, useState } from 'react'
import type { ComponentRow } from './api/scan'

type SortKey = 'name' | 'vuln_count' | 'severity'

const FILTERS = ['Critical', 'High', 'Medium', 'Low', 'Unknown', 'None', 'Not checked']

const BADGE: Record<string, string> = {
  Critical: 'bg-red-100 text-red-800 ring-red-600/30',
  High: 'bg-orange-100 text-orange-800 ring-orange-600/30',
  Medium: 'bg-yellow-100 text-yellow-800 ring-yellow-600/30',
  Low: 'bg-blue-100 text-blue-800 ring-blue-600/30',
  Unknown: 'bg-gray-100 text-gray-700 ring-gray-400/30',
  None: 'bg-green-100 text-green-800 ring-green-600/30',
  'Not checked': 'bg-gray-50 text-gray-500 ring-gray-300/30',
}

export default function ResultsTable({ components }: { components: ComponentRow[] }) {
  const [filter, setFilter] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('severity')
  const [desc, setDesc] = useState(true)

  const rows = useMemo(() => {
    const shown = filter === 'all' ? components : components.filter((c) => c.severity === filter)
    const value = (c: ComponentRow) =>
      sortKey === 'name' ? c.name.toLowerCase() : sortKey === 'vuln_count' ? (c.vuln_count ?? -1) : c.rank
    return [...shown].sort((a, b) => {
      const x = value(a)
      const y = value(b)
      if (x < y) return desc ? 1 : -1
      if (x > y) return desc ? -1 : 1
      return 0
    })
  }, [components, filter, sortKey, desc])

  const clickHeader = (key: SortKey) => {
    if (key === sortKey) {
      setDesc(!desc)
    } else {
      setSortKey(key)
      setDesc(key !== 'name') // numbers start worst-first, names start A-Z
    }
  }

  const arrow = (key: SortKey) => (key === sortKey ? (desc ? ' ▼' : ' ▲') : '')

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-600">
          Showing {rows.length} of {components.length} components
        </p>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          Severity
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-lg border border-gray-300 px-2 py-1.5 text-sm"
          >
            <option value="all">All</option>
            {FILTERS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-left text-gray-600">
            <tr>
              <th className="cursor-pointer px-3 py-2 font-medium" onClick={() => clickHeader('name')}>
                Name{arrow('name')}
              </th>
              <th className="px-3 py-2 font-medium">Version</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="cursor-pointer px-3 py-2 font-medium" onClick={() => clickHeader('vuln_count')}>
                Vulnerabilities{arrow('vuln_count')}
              </th>
              <th className="cursor-pointer px-3 py-2 font-medium" onClick={() => clickHeader('severity')}>
                Severity{arrow('severity')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {rows.map((c, i) => (
              <tr key={`${c.purl ?? c.name}-${i}`}>
                <td className="px-3 py-2 font-medium text-gray-900" title={c.purl ?? ''}>
                  {c.name}
                </td>
                <td className="px-3 py-2 text-gray-600">{c.version ?? 'N/A'}</td>
                <td className="px-3 py-2 text-gray-600">{c.type}</td>
                <td className="px-3 py-2 text-gray-900">{c.vuln_count ?? 'N/A'}</td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${BADGE[c.severity] ?? BADGE.Unknown}`}
                  >
                    {c.severity}
                  </span>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-gray-500">
                  No components match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}