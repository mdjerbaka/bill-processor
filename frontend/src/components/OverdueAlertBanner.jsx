import { ExclamationTriangleIcon, CheckCircleIcon } from '@heroicons/react/24/outline'

function getSeverity(daysOverdue) {
  if (daysOverdue >= 25) return 'critical'
  if (daysOverdue >= 15) return 'alert'
  return 'warning'
}

const severityStyles = {
  warning: {
    container: 'bg-amber-900/40 border-amber-500/60',
    badge: 'bg-amber-500 text-black',
    text: 'text-amber-300',
    label: 'PAST DUE',
    animate: '',
  },
  alert: {
    container: 'bg-orange-900/40 border-orange-500/60',
    badge: 'bg-orange-500 text-black',
    text: 'text-orange-300',
    label: 'PAST DUE',
    animate: 'animate-pulse',
  },
  critical: {
    container: 'bg-red-900/50 border-red-500/70',
    badge: 'bg-red-600 text-white',
    text: 'text-red-300',
    label: 'CREDIT DANGER',
    animate: 'animate-pulse',
  },
}

export default function OverdueAlertBanner({ overdueBills, onMarkPaid }) {
  if (!overdueBills || overdueBills.length === 0) return null

  // Sort: most critical first
  const sorted = [...overdueBills].sort((a, b) => (b.days_overdue || 0) - (a.days_overdue || 0))

  const hasCritical = sorted.some(b => (b.days_overdue || 0) >= 25)
  const hasAlert = sorted.some(b => (b.days_overdue || 0) >= 15)

  const bannerBg = hasCritical
    ? 'bg-red-950/80 border-red-500'
    : hasAlert
    ? 'bg-orange-950/80 border-orange-500'
    : 'bg-amber-950/80 border-amber-500'

  const bannerGlow = hasCritical
    ? 'shadow-[0_0_30px_rgba(239,68,68,0.3)]'
    : ''

  return (
    <div className={`${bannerBg} ${bannerGlow} border-2 rounded-xl p-4 mb-6 ${hasCritical ? 'animate-pulse' : ''}`}>
      <div className="flex items-center gap-2 mb-3">
        <ExclamationTriangleIcon className={`h-6 w-6 ${hasCritical ? 'text-red-400' : hasAlert ? 'text-orange-400' : 'text-amber-400'}`} />
        <h3 className={`text-lg font-bold ${hasCritical ? 'text-red-300' : hasAlert ? 'text-orange-300' : 'text-amber-300'}`}>
          {sorted.length} Overdue Bill{sorted.length !== 1 ? 's' : ''} — Action Required
        </h3>
      </div>
      <div className="space-y-2">
        {sorted.map((bill) => {
          const severity = getSeverity(bill.days_overdue || 0)
          const styles = severityStyles[severity]
          return (
            <div
              key={bill.id}
              className={`flex items-center justify-between p-3 rounded-lg border ${styles.container} ${styles.animate}`}
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${styles.badge} whitespace-nowrap`}>
                  {styles.label}
                </span>
                {!bill.is_auto_pay && (
                  <span className="px-2 py-0.5 rounded text-xs font-bold bg-purple-600 text-white whitespace-nowrap">
                    MANUAL PAY
                  </span>
                )}
                <div className="min-w-0">
                  <span className={`font-semibold ${styles.text} block truncate`}>{bill.bill_name}</span>
                  <span className="text-xs text-gray-400 block truncate">{bill.vendor_name}</span>
                </div>
              </div>
              <div className="flex items-center gap-4 flex-shrink-0 ml-4">
                <span className={`font-bold ${styles.text}`}>
                  ${(bill.amount || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
                <span className={`text-sm font-semibold ${styles.text} whitespace-nowrap`}>
                  {bill.days_overdue}d overdue
                </span>
                {onMarkPaid && (
                  <button
                    onClick={() => onMarkPaid(bill.id)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-900/60 text-emerald-400 hover:bg-emerald-800 transition-colors whitespace-nowrap"
                  >
                    <CheckCircleIcon className="h-4 w-4" />
                    Mark Paid
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
