import {
  CheckCircleIcon,
  EnvelopeIcon,
  CreditCardIcon,
  DocumentMagnifyingGlassIcon,
  WrenchScrewdriverIcon,
  ArrowTopRightOnSquareIcon,
  InformationCircleIcon,
  BoltIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'
import { useState } from 'react'
import { Link } from 'react-router-dom'

function Section({ icon: Icon, title, color, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 p-6 text-left hover:bg-gray-750 transition-colors"
      >
        <div className={`p-2.5 rounded-lg ${color}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
        </div>
        {open ? (
          <ChevronDownIcon className="h-5 w-5 text-gray-400" />
        ) : (
          <ChevronRightIcon className="h-5 w-5 text-gray-400" />
        )}
      </button>
      {open && (
        <div className="px-6 pb-6 text-gray-300 text-sm leading-relaxed space-y-4 border-t border-gray-700 pt-4">
          {children}
        </div>
      )}
    </div>
  )
}

function Step({ number, title, children }) {
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center mt-0.5">
        {number}
      </div>
      <div className="flex-1">
        <p className="font-medium text-gray-100 mb-1">{title}</p>
        <div className="text-gray-400 space-y-2">{children}</div>
      </div>
    </div>
  )
}

function Tip({ children }) {
  return (
    <div className="flex gap-2 bg-blue-900/30 border border-blue-800/50 rounded-lg p-3 text-blue-200 text-xs">
      <InformationCircleIcon className="h-4 w-4 flex-shrink-0 mt-0.5" />
      <div>{children}</div>
    </div>
  )
}

export default function HelpPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-100">Setup Guide</h1>
        <p className="text-gray-400 mt-2">
          Follow these steps to get Bill Processor fully configured. Most settings
          are managed on the{' '}
          <Link to="/settings" className="text-blue-400 hover:text-blue-300 underline">
            Settings
          </Link>{' '}
          page.
        </p>
      </div>

      {/* ── Quick Start ── */}
      <Section
        icon={BoltIcon}
        title="Quick Start Overview"
        color="bg-green-600"
        defaultOpen={true}
      >
        <p>
          Bill Processor automates your invoice workflow: emails arrive → invoices are
          extracted via OCR → matched to jobs → sent to QuickBooks as bills. Here's the
          setup flow:
        </p>
        <ol className="list-decimal list-inside space-y-1 text-gray-300">
          <li><strong>Connect your email</strong> — so the app can read invoice emails</li>
          <li><strong>Configure OCR</strong> — so invoices can be read from PDFs/images</li>
          <li><strong>Connect QuickBooks</strong> — so bills are synced to your accounting</li>
          <li><strong>Add your jobs</strong> — so invoices get matched to the right project</li>
        </ol>
        <Tip>
          All configuration is done right here in the app — no files to edit.
          Head to <Link to="/settings" className="text-blue-300 underline">Settings</Link> to get started.
        </Tip>
      </Section>

      {/* ── Step 1: Email ── */}
      <Section
        icon={EnvelopeIcon}
        title="Step 1 — Connect Your Email"
        color="bg-purple-600"
      >
        <p>
          Bill Processor polls your email inbox every 30 seconds for new invoice
          attachments (PDFs, images). You can connect via <strong>Microsoft 365</strong> (recommended)
          or traditional <strong>IMAP</strong>.
        </p>

        <h3 className="text-gray-100 font-semibold mt-4">Option A: Microsoft 365 (Recommended)</h3>
        <div className="space-y-3 ml-1">
          <Step number="1" title="Get your Microsoft app credentials">
            <p>
              Go to the{' '}
              <a href="https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
                target="_blank" rel="noopener noreferrer"
                className="text-blue-400 underline inline-flex items-center gap-1">
                Azure Portal — App Registrations
                <ArrowTopRightOnSquareIcon className="h-3 w-3" />
              </a>
            </p>
            <p>Click <strong>"New registration"</strong>:</p>
            <ul className="list-disc ml-4 space-y-1">
              <li>Name: <code className="bg-gray-700 px-1 rounded text-xs">Bill Processor</code></li>
              <li>Supported account types: <strong>Single tenant</strong> (your org only)</li>
              <li>Redirect URI: <strong>Web</strong> → <code className="bg-gray-700 px-1 rounded text-xs">http://localhost:8000/api/v1/microsoft/callback</code></li>
            </ul>
          </Step>
          <Step number="2" title="Add API permissions">
            <p>In your app registration, go to <strong>API permissions</strong> → <strong>Add a permission</strong> → <strong>Microsoft Graph</strong> → <strong>Delegated</strong>:</p>
            <ul className="list-disc ml-4 space-y-1">
              <li><code className="bg-gray-700 px-1 rounded text-xs">Mail.Read</code> — read emails</li>
              <li><code className="bg-gray-700 px-1 rounded text-xs">Mail.ReadWrite</code> — mark emails as read</li>
              <li><code className="bg-gray-700 px-1 rounded text-xs">User.Read</code> — usually pre-added</li>
            </ul>
            <p>Click <strong>"Grant admin consent"</strong> after adding.</p>
          </Step>
          <Step number="3" title="Create a client secret">
            <p>Go to <strong>Certificates & secrets</strong> → <strong>New client secret</strong>. Copy the <strong>Value</strong> immediately (it won't be shown again).</p>
          </Step>
          <Step number="4" title="Enter credentials in the app">
            <p>
              Go to{' '}
              <Link to="/settings" className="text-blue-400 underline">Settings</Link>
              {' '}→ <strong>Microsoft 365 Email</strong> section. Enter:
            </p>
            <ul className="list-disc ml-4 space-y-1">
              <li><strong>Application (client) ID</strong> — from the Overview page</li>
              <li><strong>Client Secret</strong> — the value you just created</li>
              <li><strong>Tenant ID</strong> — from the Overview page (or <code className="bg-gray-700 px-1 rounded text-xs">common</code>)</li>
            </ul>
            <p>Click <strong>"Connect Microsoft 365"</strong> and sign in when prompted.</p>
          </Step>
        </div>

        <h3 className="text-gray-100 font-semibold mt-6">Option B: IMAP (Gmail, Yahoo, Other)</h3>
        <div className="space-y-3 ml-1">
          <Step number="1" title="Get your IMAP settings">
            <p>Common providers:</p>
            <table className="w-full text-xs mt-2 border border-gray-700 rounded">
              <thead>
                <tr className="bg-gray-700/50">
                  <th className="px-3 py-1.5 text-left">Provider</th>
                  <th className="px-3 py-1.5 text-left">IMAP Host</th>
                  <th className="px-3 py-1.5 text-left">Port</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-gray-700"><td className="px-3 py-1.5">Gmail</td><td className="px-3 py-1.5">imap.gmail.com</td><td className="px-3 py-1.5">993</td></tr>
                <tr className="border-t border-gray-700"><td className="px-3 py-1.5">Outlook/Hotmail</td><td className="px-3 py-1.5">outlook.office365.com</td><td className="px-3 py-1.5">993</td></tr>
                <tr className="border-t border-gray-700"><td className="px-3 py-1.5">Yahoo</td><td className="px-3 py-1.5">imap.mail.yahoo.com</td><td className="px-3 py-1.5">993</td></tr>
              </tbody>
            </table>
          </Step>
          <Step number="2" title="Enable app passwords (if using Gmail)">
            <p>
              Gmail requires an{' '}
              <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer"
                className="text-blue-400 underline inline-flex items-center gap-1">
                App Password
                <ArrowTopRightOnSquareIcon className="h-3 w-3" />
              </a>
              {' '}(not your regular password). Enable 2-Step Verification first, then create an app password.
            </p>
          </Step>
          <Step number="3" title="Enter credentials in the app">
            <p>Go to <Link to="/settings" className="text-blue-400 underline">Settings</Link> → <strong>Email Configuration</strong>. Enter your host, port, email address, and password. Click <strong>"Save & Test"</strong>.</p>
          </Step>
        </div>

        <Tip>
          The app checks for new emails every 30 seconds. You can also click <strong>"Poll Now"</strong> on the Dashboard or Settings page to check immediately.
        </Tip>
      </Section>

      {/* ── Step 2: OCR ── */}
      <Section
        icon={DocumentMagnifyingGlassIcon}
        title="Step 2 — Configure OCR (Invoice Reading)"
        color="bg-amber-600"
      >
        <p>
          OCR (Optical Character Recognition) extracts vendor names, amounts, dates,
          and line items from PDF/image invoices. Choose one provider:
        </p>

        <h3 className="text-gray-100 font-semibold mt-4">Option A: OpenAI (Recommended)</h3>
        <div className="space-y-3 ml-1">
          <Step number="1" title="Get an OpenAI API key">
            <p>
              Go to{' '}
              <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer"
                className="text-blue-400 underline inline-flex items-center gap-1">
                OpenAI API Keys
                <ArrowTopRightOnSquareIcon className="h-3 w-3" />
              </a>
              {' '}and create a new key. Add a small credit balance ($5-10 is plenty for hundreds of invoices).
            </p>
          </Step>
          <Step number="2" title="Enter it in the app">
            <p>Go to <Link to="/settings" className="text-blue-400 underline">Settings</Link> → <strong>OCR Configuration</strong>. Select <strong>OpenAI</strong> as the provider and paste your API key. Click <strong>"Save"</strong>.</p>
          </Step>
        </div>

        <h3 className="text-gray-100 font-semibold mt-6">Option B: Azure Document Intelligence</h3>
        <div className="space-y-3 ml-1">
          <Step number="1" title="Create an Azure resource">
            <p>
              In the{' '}
              <a href="https://portal.azure.com/#create/Microsoft.CognitiveServicesFormRecognizer" target="_blank" rel="noopener noreferrer"
                className="text-blue-400 underline inline-flex items-center gap-1">
                Azure Portal
                <ArrowTopRightOnSquareIcon className="h-3 w-3" />
              </a>
              , create a <strong>Document Intelligence</strong> resource. The free tier (F0) handles 500 pages/month.
            </p>
          </Step>
          <Step number="2" title="Enter credentials">
            <p>Go to <Link to="/settings" className="text-blue-400 underline">Settings</Link> → <strong>OCR Configuration</strong>. Select <strong>Azure</strong>, enter your endpoint URL and API key.</p>
          </Step>
        </div>

        <Tip>
          <strong>Cost estimate:</strong> OpenAI costs roughly $0.01–0.03 per invoice page. For a
          typical small business processing 50–100 invoices/month, expect $1–5/month.
        </Tip>
      </Section>

      {/* ── Step 3: QuickBooks ── */}
      <Section
        icon={CreditCardIcon}
        title="Step 3 — Connect QuickBooks"
        color="bg-blue-600"
      >
        <p>
          Connecting QuickBooks allows the app to automatically create bills from
          extracted invoices and sync payments.
        </p>

        <div className="space-y-3 ml-1">
          <Step number="1" title="Create a QuickBooks app">
            <p>
              Go to the{' '}
              <a href="https://developer.intuit.com/app/developer/dashboard" target="_blank" rel="noopener noreferrer"
                className="text-blue-400 underline inline-flex items-center gap-1">
                Intuit Developer Dashboard
                <ArrowTopRightOnSquareIcon className="h-3 w-3" />
              </a>
            </p>
            <ul className="list-disc ml-4 space-y-1">
              <li>Click <strong>"Create an app"</strong> → Select <strong>"QuickBooks Online and Payments"</strong></li>
              <li>App name: <code className="bg-gray-700 px-1 rounded text-xs">Bill Processor</code></li>
              <li>Select the scopes: <strong>Accounting</strong></li>
            </ul>
          </Step>
          <Step number="2" title="Configure redirect URI">
            <p>In your app settings, go to <strong>Keys & credentials</strong> (use the <strong>Production</strong> tab for real data).</p>
            <p>Add this redirect URI:</p>
            <code className="block bg-gray-700 px-3 py-2 rounded text-xs text-green-300 mt-1">
              http://localhost:8000/api/v1/quickbooks/callback
            </code>
          </Step>
          <Step number="3" title="Copy your Client ID and Secret">
            <p>From the <strong>Keys & credentials</strong> page, copy:</p>
            <ul className="list-disc ml-4 space-y-1">
              <li><strong>Client ID</strong></li>
              <li><strong>Client Secret</strong></li>
            </ul>
          </Step>
          <Step number="4" title="Enter credentials and connect">
            <p>Go to <Link to="/settings" className="text-blue-400 underline">Settings</Link> → <strong>QuickBooks Configuration</strong>.</p>
            <ul className="list-disc ml-4 space-y-1">
              <li>Paste the Client ID and Client Secret</li>
              <li>Set Environment to <strong>Production</strong> (or Sandbox for testing)</li>
              <li>Click <strong>"Save Credentials"</strong></li>
              <li>Click <strong>"Connect to QuickBooks"</strong> and authorize when prompted</li>
            </ul>
          </Step>
          <Step number="5" title="Set default accounts">
            <p>After connecting, select your default <strong>Expense Account</strong> (where bills are categorized) and <strong>Bank Account</strong> (for payments). Click <strong>"Save Defaults"</strong>.</p>
          </Step>
        </div>

        <Tip>
          <strong>Sandbox vs Production:</strong> Use <strong>Sandbox</strong> to test with
          fake data. Switch to <strong>Production</strong> when ready for real invoices.
          You'll need to re-enter credentials and reconnect when switching.
        </Tip>
      </Section>

      {/* ── Step 4: Jobs ── */}
      <Section
        icon={WrenchScrewdriverIcon}
        title="Step 4 — Add Your Jobs"
        color="bg-teal-600"
      >
        <p>
          Jobs represent your active projects or service addresses. The app matches
          incoming invoices to jobs based on vendor name and service address.
        </p>

        <div className="space-y-3 ml-1">
          <Step number="1" title="Navigate to the Jobs page">
            <p>Click <Link to="/jobs" className="text-blue-400 underline">Jobs</Link> in the sidebar, or upload a CSV.</p>
          </Step>
          <Step number="2" title="Add jobs manually or import CSV">
            <p>Each job needs:</p>
            <ul className="list-disc ml-4 space-y-1">
              <li><strong>Job Name</strong> — e.g., "Smith Kitchen Renovation"</li>
              <li><strong>Job Number</strong> — your internal reference number</li>
              <li><strong>Address</strong> — service/project address (used for matching)</li>
            </ul>
            <p className="mt-2">
              For CSV import, use columns: <code className="bg-gray-700 px-1 rounded text-xs">name</code>,{' '}
              <code className="bg-gray-700 px-1 rounded text-xs">number</code>,{' '}
              <code className="bg-gray-700 px-1 rounded text-xs">address</code>
            </p>
          </Step>
          <Step number="3" title="How matching works">
            <p>When a new invoice arrives, the app tries to match it to a job using:</p>
            <ul className="list-disc ml-4 space-y-1">
              <li><strong>Address matching</strong> — compares the invoice's service address against job addresses (≥90% confidence)</li>
              <li><strong>Vendor mapping</strong> — if you've previously assigned a vendor to a job, future invoices from that vendor auto-match (≥95% confidence)</li>
            </ul>
            <p className="mt-2">
              Invoices that match with high confidence are <strong>auto-sent to QuickBooks</strong> as bills.
              Lower-confidence matches show as <strong>"needs review"</strong> on the Invoices page.
            </p>
          </Step>
        </div>

        <Tip>
          The more jobs you add, the better the auto-matching works. You can also
          manually assign invoices to jobs from the invoice detail page.
        </Tip>
      </Section>

      {/* ── Workflow ── */}
      <Section
        icon={CheckCircleIcon}
        title="How the Daily Workflow Works"
        color="bg-indigo-600"
      >
        <p className="font-medium text-gray-100">Once everything is set up, here's what happens automatically:</p>

        <div className="space-y-2 mt-3">
          <div className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 mt-2 flex-shrink-0" />
            <p><strong>Every 30 seconds</strong> — the app checks your email for new invoices</p>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 mt-2 flex-shrink-0" />
            <p><strong>Attachments are extracted</strong> — PDFs and images are read by OCR</p>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 mt-2 flex-shrink-0" />
            <p><strong>Invoices are matched to jobs</strong> — by address or vendor history</p>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 mt-2 flex-shrink-0" />
            <p><strong>High-confidence matches → auto-sent</strong> to QuickBooks as bills</p>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-2 flex-shrink-0" />
            <p><strong>Low-confidence matches → "needs review"</strong> on the Invoices page for you to assign manually</p>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 mt-2 flex-shrink-0" />
            <p><strong>Mark invoices as paid</strong> in the app → payment syncs to QuickBooks</p>
          </div>
        </div>

        <h3 className="text-gray-100 font-semibold mt-6">Page Breakdown</h3>
        <div className="space-y-2 mt-2">
          <p><Link to="/" className="text-blue-400 underline font-medium">Dashboard</Link> — Overview of recent invoices, outstanding amounts, and system health. Use <strong>"Poll Now"</strong> to manually check for new emails.</p>
          <p><Link to="/invoices" className="text-blue-400 underline font-medium">Invoices</Link> — All extracted invoices. Filter by status. Click any invoice to see details, assign to a job, approve, or send to QuickBooks.</p>
          <p><Link to="/payables" className="text-blue-400 underline font-medium">Payables</Link> — Bills that have been sent to QuickBooks. Track outstanding vs. paid. Export to CSV.</p>
          <p><Link to="/jobs" className="text-blue-400 underline font-medium">Jobs</Link> — Manage your projects/addresses. Add, edit, or import from CSV.</p>
          <p><Link to="/settings" className="text-blue-400 underline font-medium">Settings</Link> — Configure email, OCR, QuickBooks, and Microsoft 365 connections.</p>
          <p><Link to="/junk" className="text-blue-400 underline font-medium">Junk Bin</Link> — Non-invoice attachments and dismissed items. You can restore anything accidentally junked.</p>
        </div>
      </Section>

      {/* ── Troubleshooting ── */}
      <Section
        icon={InformationCircleIcon}
        title="Troubleshooting"
        color="bg-red-600"
      >
        <div className="space-y-4">
          <div>
            <p className="font-medium text-gray-100">No new invoices appearing?</p>
            <ul className="list-disc ml-4 mt-1 space-y-1">
              <li>Check that your email is connected in <Link to="/settings" className="text-blue-400 underline">Settings</Link></li>
              <li>Click "Poll Now" on the Dashboard or Settings page</li>
              <li>Make sure invoices are sent as <strong>PDF or image attachments</strong> (not inline text)</li>
              <li>Only <strong>unread</strong> emails are processed — mark old emails as unread to reprocess</li>
            </ul>
          </div>

          <div>
            <p className="font-medium text-gray-100">Invoices showing $0 or wrong amounts?</p>
            <ul className="list-disc ml-4 mt-1 space-y-1">
              <li>This usually means OCR couldn't read the PDF. Check that your OCR API key is valid in Settings</li>
              <li>Try a different OCR provider (OpenAI generally works best)</li>
              <li>Scanned/photographed invoices work, but cleaner PDFs give better results</li>
            </ul>
          </div>

          <div>
            <p className="font-medium text-gray-100">QuickBooks not syncing?</p>
            <ul className="list-disc ml-4 mt-1 space-y-1">
              <li>Check the QB connection status in <Link to="/settings" className="text-blue-400 underline">Settings</Link></li>
              <li>QB tokens expire periodically — click <strong>"Reconnect"</strong> if disconnected</li>
              <li>Make sure you've set default expense and bank accounts</li>
            </ul>
          </div>

          <div>
            <p className="font-medium text-gray-100">Invoices stuck on "needs review"?</p>
            <ul className="list-disc ml-4 mt-1 space-y-1">
              <li>The invoice didn't match any job automatically</li>
              <li>Click the invoice → assign it to a job → click <strong>"Approve"</strong></li>
              <li>Future invoices from the same vendor will auto-match</li>
            </ul>
          </div>

          <div>
            <p className="font-medium text-gray-100">Need to reset and start over?</p>
            <ul className="list-disc ml-4 mt-1 space-y-1">
              <li>Go to <Link to="/settings" className="text-blue-400 underline">Settings</Link> → scroll to the bottom for <strong>"Reset Invoice Data"</strong> and <strong>"Reset Job Data"</strong></li>
              <li>This clears processed invoices/jobs but keeps your email, OCR, and QuickBooks configuration</li>
            </ul>
          </div>
        </div>
      </Section>

      <div className="text-center text-gray-500 text-xs pb-8 pt-2">
        Bill Processor v0.1.0
      </div>
    </div>
  )
}
