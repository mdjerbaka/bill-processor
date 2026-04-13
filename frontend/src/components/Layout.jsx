import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import { payablesAPI } from '../services/api'
import NotificationBell from './NotificationBell'
import {
  InboxIcon,
  CurrencyDollarIcon,
  Cog6ToothIcon,
  HomeIcon,
  TrashIcon,
  ArrowRightOnRectangleIcon,
  CalendarDaysIcon,
  Bars3Icon,
  XMarkIcon,
  DocumentCheckIcon,
  BanknotesIcon,
  ClockIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Receivables', href: '/receivables', icon: DocumentCheckIcon },
  { name: 'Payments Out', href: '/payments-out', icon: BanknotesIcon },
  { name: 'Payment History', href: '/payment-history', icon: ClockIcon },
  { name: 'Invoices to be Reviewed', href: '/invoices-review', icon: EyeIcon },
  { name: 'Payables', href: '/payables', icon: CurrencyDollarIcon },
  { name: 'Recurring Bills', href: '/bills', icon: CalendarDaysIcon },
]

export default function Layout() {
  const { logout } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [balance, setBalance] = useState(null)
  const location = useLocation()

  const fetchBalance = useCallback(async () => {
    try {
      const res = await payablesAPI.getRealBalance()
      setBalance(res.data)
    } catch {}
  }, [])

  // Close sidebar on navigation, refetch balance
  useEffect(() => {
    setSidebarOpen(false)
    fetchBalance()
  }, [location.pathname, fetchBalance])

  // Fetch balance on mount and every 30 seconds
  useEffect(() => {
    fetchBalance()
    const interval = setInterval(fetchBalance, 30000)
    return () => clearInterval(interval)
  }, [fetchBalance])

  // Listen for balance-changed events from child pages
  useEffect(() => {
    const handler = () => fetchBalance()
    window.addEventListener('balance-changed', handler)
    return () => window.removeEventListener('balance-changed', handler)
  }, [fetchBalance])

  return (
    <div className="min-h-screen flex">
      {/* Mobile hamburger button */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="md:hidden fixed top-4 left-4 z-50 p-2 bg-gray-800 rounded-lg text-gray-300 hover:text-white"
      >
        <Bars3Icon className="h-6 w-6" />
      </button>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed md:static inset-y-0 left-0 z-50
        w-64 bg-gray-900 text-white flex flex-col
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
      `}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-3">
            <img src="/logo.avif" alt="Logo" className="h-12 w-auto" />
            <button
              onClick={() => setSidebarOpen(false)}
              className="md:hidden p-1 text-gray-400 hover:text-white"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">Bill Processor</h1>
              <p className="text-gray-400 text-sm mt-1">Invoice Automation</p>
            </div>
            <NotificationBell />
          </div>
        </div>

        <nav className="flex-1 px-4 space-y-1">
          {balance && (
            <div className="mb-3 px-3 py-2.5 bg-gray-800 rounded-lg">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Real Balance</p>
              <p className={`text-lg font-bold ${balance.real_available >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ${parseFloat(balance.real_available).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
              <div className="mt-1 text-xs text-gray-500 space-y-0.5">
                <p>Bank: ${parseFloat(balance.bank_balance).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
                <p>Receivables: +${parseFloat(balance.total_receivables || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
                <p>Payments Out: -${parseFloat(balance.total_payments_out || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
                <p>Locked Bills: -${parseFloat(balance.total_locked_bills || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
                <p>Included Payables: -${parseFloat(balance.total_included_payables || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
                <p>Included Bills: -${parseFloat(balance.total_included_bills || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
                <p>Vendor Accounts: -${parseFloat(balance.total_included_vendors || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
                <p>Buffer: -${parseFloat(balance.buffer || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
              </div>
            </div>
          )}
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              end={item.href === '/'}
              className={({ isActive }) =>
                `flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <item.icon className="h-5 w-5 mr-3" />
              {item.name}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-800">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `flex items-center px-3 py-2 text-sm rounded-lg transition-colors mb-2 ${
                isActive
                  ? 'bg-gray-800 text-gray-200'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
              }`
            }
          >
            <Cog6ToothIcon className="h-4 w-4 mr-3" />
            Settings
          </NavLink>
          <NavLink
            to="/junk"
            className={({ isActive }) =>
              `flex items-center px-3 py-2 text-sm rounded-lg transition-colors mb-2 ${
                isActive
                  ? 'bg-gray-800 text-gray-200'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
              }`
            }
          >
            <TrashIcon className="h-4 w-4 mr-3" />
            Junk Bin
          </NavLink>
          <button
            onClick={logout}
            className="flex items-center w-full px-3 py-2 text-sm text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
          >
            <ArrowRightOnRectangleIcon className="h-5 w-5 mr-3" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-950 md:ml-0">
        <div className="p-4 pt-16 md:pt-8 md:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
