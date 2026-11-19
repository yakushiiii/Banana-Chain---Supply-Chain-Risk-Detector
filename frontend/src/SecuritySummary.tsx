import type { ComponentRow } from './api/scan'

type SecuritySummaryProps = {
  components: ComponentRow[]
  vulnsOk: boolean
}

export default function SecuritySummary({ components, vulnsOk }: SecuritySummaryProps) {
  const criticalCount = components.filter((c) => c.severity === 'Critical').length
  const highCount = components.filter((c) => c.severity === 'High').length
  const mediumCount = components.filter((c) => c.severity === 'Medium').length
  const lowCount = components.filter((c) => c.severity === 'Low').length
  const safeCount = components.filter((c) => c.severity === 'None').length

  const totalVulnerableComponents = criticalCount + highCount + mediumCount + lowCount

  const posture = (() => {
    if (!vulnsOk) return { label: 'Vulnerability Check Offline', badge: 'bg-gray-100 text-gray-700 ring-gray-400/30' }
    if (components.length === 0) return { label: 'No Dependencies Found', badge: 'bg-gray-100 text-gray-700 ring-gray-400/30' }
    if (criticalCount > 0) return { label: 'Critical Risk', badge: 'bg-red-50 text-red-700 ring-red-600/30' }
    if (highCount > 0) return { label: 'High Risk', badge: 'bg-orange-50 text-orange-700 ring-orange-600/30' }
    if (mediumCount > 0) return { label: 'Moderate Risk', badge: 'bg-yellow-50 text-yellow-700 ring-yellow-600/30' }
    if (lowCount > 0) return { label: 'Low Risk', badge: 'bg-blue-50 text-blue-700 ring-blue-600/30' }
    return { label: 'Secure (No Known Risks)', badge: 'bg-green-50 text-green-700 ring-green-600/30' }
  })()

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
        <div>
          <span className="text-sm font-medium text-gray-600">Security Posture</span>
          <p className="text-xs text-gray-500">
            {totalVulnerableComponents > 0
              ? `${totalVulnerableComponents} of ${components.length} components flagged with known vulnerabilities`
              : `All ${components.length} components have no known vulnerabilities`}
          </p>
        </div>
        <div>
          <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${posture.badge}`}>
            {posture.label}
          </span>
        </div>
      </div>

      {/* Metrics Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="rounded-lg border border-gray-200 bg-white p-3 text-center shadow-xs">
          <p className="text-xs font-medium text-gray-500">Total Packages</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{components.length}</p>
        </div>

        <div className="rounded-lg border border-red-200 bg-red-50/50 p-3 text-center shadow-xs">
          <p className="text-xs font-medium text-red-700">Critical</p>
          <p className="mt-1 text-2xl font-bold text-red-700">{criticalCount}</p>
        </div>

        <div className="rounded-lg border border-orange-200 bg-orange-50/50 p-3 text-center shadow-xs">
          <p className="text-xs font-medium text-orange-700">High</p>
          <p className="mt-1 text-2xl font-bold text-orange-700">{highCount}</p>
        </div>

        <div className="rounded-lg border border-yellow-200 bg-yellow-50/50 p-3 text-center shadow-xs">
          <p className="text-xs font-medium text-yellow-700">Medium</p>
          <p className="mt-1 text-2xl font-bold text-yellow-700">{mediumCount}</p>
        </div>

        <div className="rounded-lg border border-green-200 bg-green-50/50 p-3 text-center shadow-xs col-span-2 sm:col-span-1">
          <p className="text-xs font-medium text-green-700">Clean / Safe</p>
          <p className="mt-1 text-2xl font-bold text-green-700">{safeCount}</p>
        </div>
      </div>

      {/* Visual Health Ratio Bar */}
      {components.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <div className="flex justify-between text-xs text-gray-500">
            <span>Dependency Health Breakdown</span>
            <span>{Math.round((safeCount / components.length) * 100)}% Secure</span>
          </div>
          <div className="flex h-2 w-full overflow-hidden rounded-full bg-gray-200">
            {criticalCount > 0 && (
              <div
                style={{ width: `${(criticalCount / components.length) * 100}%` }}
                className="bg-red-500"
                title={`${criticalCount} Critical`}
              />
            )}
            {highCount > 0 && (
              <div
                style={{ width: `${(highCount / components.length) * 100}%` }}
                className="bg-orange-500"
                title={`${highCount} High`}
              />
            )}
            {mediumCount > 0 && (
              <div
                style={{ width: `${(mediumCount / components.length) * 100}%` }}
                className="bg-yellow-400"
                title={`${mediumCount} Medium`}
              />
            )}
            {lowCount > 0 && (
              <div
                style={{ width: `${(lowCount / components.length) * 100}%` }}
                className="bg-blue-400"
                title={`${lowCount} Low`}
              />
            )}
            {safeCount > 0 && (
              <div
                style={{ width: `${(safeCount / components.length) * 100}%` }}
                className="bg-green-500"
                title={`${safeCount} Clean`}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
