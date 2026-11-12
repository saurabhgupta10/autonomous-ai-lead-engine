'use client'

import {
  Activity,
  AlertCircle,
  Bell,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileText,
  Filter,
  LayoutDashboard,
  Loader2,
  Mail,
  Menu,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  X,
  Zap,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface RawLeadRecord {
  [key: string]: any
}

interface LeadItem {
  id: string
  timestamp: string
  company: string
  website: string
  email: string
  priority: 'High' | 'Medium' | 'Low' | 'Unscored' | string
  summary: string
  initials: string
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Page() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'Overview' | 'Lead Feed' | 'AI Insights' | 'Campaigns'>('Overview')
  
  // Data state
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState<string | null>(null)
  const [agentModel, setAgentModel] = useState<string>('Gemini Engine')
  const [lastSyncTime, setLastSyncTime] = useState<string>('Never')

  // Search, filter & sort state
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [priorityFilter, setPriorityFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All')
  const [sortDescending, setSortDescending] = useState(true)

  // Scan state
  const [isScanning, setIsScanning] = useState(false)
  const [scanNotification, setScanNotification] = useState<{ message: string; type: 'success' | 'info' | 'error' } | null>(null)

  // Normalize backend / Google Sheets row formats into LeadItem
  const normalizeLead = (record: RawLeadRecord, index: number): LeadItem => {
    const company =
      record['Company Name'] || record.company_name || record.company || record.Company || 'Unknown Prospect'
    const timestamp =
      record['Timestamp (UTC)'] || record.timestamp || record.Captured || record.created_at || 'Recently'
    const website = record.Website || record.website || ''
    const email = record.Email || record.email || 'N/A'
    const priority = record.Priority || record.priority || 'Medium'
    const summary =
      record.Reason || record.reason || record.summary || record.AI_analysis || record.description || 'No analysis recorded.'

    const initials =
      company
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map((w: string) => w[0])
        .join('')
        .toUpperCase() || 'CO'

    return {
      id: `${company}-${index}`,
      timestamp,
      company,
      website,
      email,
      priority,
      summary,
      initials,
    }
  }

  // Fetch leads from backend
  const fetchLeads = useCallback(async () => {
    try {
      setLoading(true)
      setApiError(null)

      // Fetch health for metadata
      try {
        const healthRes = await fetch(`${API_BASE}/health`)
        if (healthRes.ok) {
          const healthData = await healthRes.json()
          if (healthData.integrations?.gemini?.model) {
            setAgentModel(healthData.integrations.gemini.model)
          }
        }
      } catch {
        // Optional metadata fetch error ignored
      }

      const res = await fetch(`${API_BASE}/api/leads`)
      if (!res.ok) {
        const errJson = await res.json().catch(() => null)
        const errMsg = errJson?.detail?.error || errJson?.detail || `API responded with status ${res.status}`
        throw new Error(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
      }

      const payload = await res.json()
      const rawData: RawLeadRecord[] = Array.isArray(payload.data) ? payload.data : []
      const parsed = rawData.map((row, idx) => normalizeLead(row, idx))
      
      setLeads(parsed)
      setLastSyncTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
    } catch (err: any) {
      setApiError(err.message || 'Could not connect to FastAPI server.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLeads()
  }, [fetchLeads])

  // Trigger lead scan pipeline
  const runAiScan = async () => {
    if (isScanning) return
    setIsScanning(true)
    setScanNotification({ message: 'Initiating lead scan & AI scoring...', type: 'info' })

    try {
      const scanRes = await fetch(`${API_BASE}/api/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dry_run: false }),
      })

      if (!scanRes.ok) {
        const errJson = await scanRes.json().catch(() => null)
        throw new Error(errJson?.detail?.error || errJson?.detail || 'Scan request failed.')
      }

      // Poll scan status until completion
      let attempts = 0
      const pollInterval = setInterval(async () => {
        attempts += 1
        try {
          const statusRes = await fetch(`${API_BASE}/api/scan/status`)
          if (statusRes.ok) {
            const statusData = await statusRes.json()
            if (statusData.status === 'complete') {
              clearInterval(pollInterval)
              setIsScanning(false)
              const sum = statusData.summary || {}
              setScanNotification({
                message: `Scan complete! Scraped ${sum.scraped || 0} leads, identified ${sum.high || 0} High priority, saved to CRM.`,
                type: 'success',
              })
              fetchLeads()
            } else if (statusData.status === 'error') {
              clearInterval(pollInterval)
              setIsScanning(false)
              setScanNotification({
                message: `Scan error: ${statusData.error || 'Pipeline failed'}`,
                type: 'error',
              })
            }
          }
        } catch {
          // ignore transient poll error
        }

        if (attempts > 30) {
          clearInterval(pollInterval)
          setIsScanning(false)
          setScanNotification({ message: 'Scan timed out. Refreshing data...', type: 'info' })
          fetchLeads()
        }
      }, 1500)
    } catch (err: any) {
      setIsScanning(false)
      setScanNotification({ message: err.message || 'Failed to trigger scan.', type: 'error' })
    }
  }

  // Filtered and sorted leads
  const processedLeads = useMemo(() => {
    let result = [...leads]

    // Workspace tab filter
    if (activeTab === 'AI Insights') {
      result = result.filter((l) => l.priority.toLowerCase() === 'high')
    }

    // Priority filter
    if (priorityFilter !== 'All') {
      result = result.filter((l) => l.priority.toLowerCase() === priorityFilter.toLowerCase())
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      result = result.filter(
        (l) =>
          l.company.toLowerCase().includes(q) ||
          l.email.toLowerCase().includes(q) ||
          l.summary.toLowerCase().includes(q) ||
          l.website.toLowerCase().includes(q)
      )
    }

    // Sort order
    result.sort((a, b) => {
      const cmp = a.timestamp.localeCompare(b.timestamp)
      return sortDescending ? -cmp : cmp
    })

    return result
  }, [leads, activeTab, priorityFilter, searchQuery, sortDescending])

  // Dynamic metrics calculations
  const totalCount = leads.length
  const highPriorityCount = leads.filter((l) => l.priority.toLowerCase() === 'high').length
  const highPercentage = totalCount > 0 ? Math.round((highPriorityCount / totalCount) * 100) : 0

  const navItems = [
    { label: 'Overview' as const, icon: LayoutDashboard },
    { label: 'Lead Feed' as const, icon: Target },
    { label: 'AI Insights' as const, icon: Sparkles },
    { label: 'Campaigns' as const, icon: TrendingUp },
  ]

  return (
    <main className="min-h-screen bg-[#080b10] text-slate-100">
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside
          className={`fixed inset-y-0 left-0 z-30 flex w-[250px] flex-col border-r border-white/[0.07] bg-[#0d1118] px-4 py-5 transition-transform duration-200 lg:static lg:translate-x-0 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <div className="flex items-center gap-3 px-3">
            <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-400 text-[#07100d] shadow-[0_0_24px_rgba(52,211,153,0.24)]">
              <Zap className="size-[18px] fill-current" />
            </div>
            <div>
              <p className="text-[14px] font-semibold tracking-tight">Lead Engine</p>
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">AI-powered growth</p>
            </div>
          </div>

          <div className="mt-10 flex flex-col gap-1">
            <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-600">Workspace</p>
            {navItems.map((item) => {
              const isActive = activeTab === item.label
              return (
                <Button
                  key={item.label}
                  variant="ghost"
                  onClick={() => setActiveTab(item.label)}
                  className={`justify-start gap-3 rounded-lg px-3 text-[13px] font-medium ${
                    isActive
                      ? 'bg-emerald-400/[0.12] text-emerald-300 hover:bg-emerald-400/[0.16] hover:text-emerald-200'
                      : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-100'
                  }`}
                >
                  <item.icon className="size-[17px]" />
                  {item.label}
                  {item.label === 'Lead Feed' && (
                    <span className="ml-auto rounded-full bg-emerald-400/15 px-2 py-0.5 text-[10px] text-emerald-300">
                      {totalCount}
                    </span>
                  )}
                  {item.label === 'AI Insights' && highPriorityCount > 0 && (
                    <span className="ml-auto rounded-full bg-violet-400/15 px-2 py-0.5 text-[10px] text-violet-300">
                      {highPriorityCount}
                    </span>
                  )}
                </Button>
              )
            })}
          </div>

          <div className="mt-8 flex flex-col gap-1">
            <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-600">Manage</p>
            <Button
              variant="ghost"
              onClick={fetchLeads}
              className="justify-start gap-3 rounded-lg px-3 text-[13px] font-medium text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"
            >
              <RefreshCw className={`size-[17px] ${loading ? 'animate-spin' : ''}`} />
              Refresh Data
            </Button>
            <Button
              variant="ghost"
              onClick={() => setPriorityFilter(priorityFilter === 'High' ? 'All' : 'High')}
              className="justify-start gap-3 rounded-lg px-3 text-[13px] font-medium text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"
            >
              <Filter className="size-[17px]" />
              Filter: {priorityFilter}
            </Button>
          </div>

          <div className="mt-auto rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] p-3">
            <div className="flex items-center gap-2">
              <span className={`size-2 rounded-full ${isScanning ? 'animate-pulse bg-amber-400 shadow-[0_0_10px_#fbbf24]' : 'bg-emerald-400 shadow-[0_0_10px_#34d399]'}`} />
              <span className="text-xs font-medium text-emerald-300">
                {isScanning ? 'Scanner Active' : 'Agent Ready'}
              </span>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
              {isScanning ? 'Extracting and scoring leads with Gemini...' : `Connected to API at ${API_BASE.replace('http://', '')}`}
            </p>
          </div>

          <div className="mt-5 flex items-center gap-3 border-t border-white/[0.07] px-2 pt-4">
            <div className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 text-[11px] font-bold">
              JD
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">Jordan Davis</p>
              <p className="truncate text-[10px] text-slate-500">Growth team</p>
            </div>
            <ChevronDown className="size-4 text-slate-600" />
          </div>
        </aside>

        {/* Main Content */}
        <section className="min-w-0 flex-1">
          {/* Header */}
          <header className="flex h-[72px] items-center justify-between border-b border-white/[0.07] px-5 sm:px-8">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="text-slate-400 lg:hidden"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Toggle sidebar"
              >
                <Menu />
              </Button>
              <div>
                <p className="text-xs text-slate-500">Autonomous Sales Pipeline</p>
                <h1 className="mt-0.5 text-lg font-semibold tracking-tight text-slate-50">
                  Dashboard <span className="text-slate-500">/</span> {activeTab}
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Search Toggle */}
              {searchOpen ? (
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search leads, emails, analysis..."
                    className="h-9 w-48 rounded-lg border border-white/[0.12] bg-[#0d1118] px-3 py-1 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-400 sm:w-64"
                    autoFocus
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 size-7 text-slate-400 hover:text-slate-100"
                    onClick={() => {
                      setSearchQuery('')
                      setSearchOpen(false)
                    }}
                  >
                    <X className="size-3.5" />
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-slate-400 hover:text-slate-100"
                  onClick={() => setSearchOpen(true)}
                  aria-label="Search"
                >
                  <Search className="size-4" />
                </Button>
              )}

              <Button
                variant="ghost"
                size="icon"
                onClick={fetchLeads}
                className="text-slate-400 hover:text-slate-100"
                aria-label="Refresh"
                title="Refresh leads"
              >
                <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>

              <div className="ml-2 hidden h-6 w-px bg-white/[0.08] sm:block" />

              {/* Run AI Scan Button */}
              <Button
                onClick={runAiScan}
                disabled={isScanning}
                className="ml-1 hidden h-9 gap-2 rounded-lg bg-emerald-400 px-3 text-xs font-semibold text-[#07100d] hover:bg-emerald-300 disabled:opacity-50 sm:flex"
              >
                {isScanning ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    Scanning...
                  </>
                ) : (
                  <>
                    <Sparkles className="size-3.5" />
                    Run AI scan
                  </>
                )}
              </Button>
            </div>
          </header>

          <div className="mx-auto max-w-[1440px] px-5 py-7 sm:px-8 lg:py-9">
            {/* Notification Banner */}
            {scanNotification && (
              <div
                className={`mb-6 flex items-center justify-between rounded-lg border px-4 py-3 text-xs ${
                  scanNotification.type === 'success'
                    ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                    : scanNotification.type === 'error'
                    ? 'border-red-400/20 bg-red-400/10 text-red-300'
                    : 'border-blue-400/20 bg-blue-400/10 text-blue-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  {scanNotification.type === 'success' ? (
                    <CheckCircle2 className="size-4" />
                  ) : (
                    <AlertCircle className="size-4" />
                  )}
                  <span>{scanNotification.message}</span>
                </div>
                <button
                  onClick={() => setScanNotification(null)}
                  className="text-slate-400 hover:text-slate-200"
                >
                  <X className="size-3.5" />
                </button>
              </div>
            )}

            {/* API Error Alert */}
            {apiError && (
              <div className="mb-6 flex items-center justify-between rounded-lg border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-xs text-amber-300">
                <div className="flex items-center gap-2">
                  <AlertCircle className="size-4 shrink-0" />
                  <span>
                    Backend communication note: {apiError}. Ensure the FastAPI server is running (`uvicorn api:app --reload`).
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchLeads}
                  className="h-7 border-amber-400/30 bg-transparent text-xs text-amber-200 hover:bg-amber-400/10"
                >
                  Retry
                </Button>
              </div>
            )}

            {/* Hero / Header text */}
            <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
                  <Activity className="size-3.5" /> Live intelligence
                </div>
                <h2 className="text-2xl font-semibold tracking-[-0.03em] text-white sm:text-[28px]">
                  Lead generation, on autopilot.
                </h2>
                <p className="mt-1.5 text-sm text-slate-500">
                  {leads.length > 0
                    ? `Your AI engine has evaluated ${leads.length} prospects with ${highPriorityCount} high-intent opportunities.`
                    : 'Ready to scan target business directories and score prospects.'}
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="size-1.5 rounded-full bg-emerald-400" />
                Last synced {lastSyncTime}
              </div>
            </div>

            {/* Dynamic Metric Cards */}
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                icon={FileText}
                label="Total scraped"
                value={String(totalCount)}
                detail="leads in CRM database"
                accent="emerald"
              />
              <MetricCard
                icon={Target}
                label="High priority"
                value={String(highPriorityCount)}
                detail={`${highPercentage}% of qualified leads`}
                accent="violet"
              />
              <MetricCard
                icon={TrendingUp}
                label="Efficiency gain"
                value="90%"
                detail="vs. manual prospecting"
                accent="blue"
              />
              <MetricCard
                icon={Bot}
                label="Active AI agent"
                value={agentModel.replace('models/', '')}
                detail="Operational · Real-time scoring"
                accent="amber"
                compact
              />
            </div>

            {/* Live Lead Table Card */}
            <Card className="mt-6 overflow-hidden border-white/[0.08] bg-[#0d1118] shadow-2xl shadow-black/10">
              <div className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-100">Live lead feed</h3>
                    <Badge className="border-emerald-400/20 bg-emerald-400/10 text-[10px] font-medium text-emerald-300 hover:bg-emerald-400/10">
                      <span className="mr-1 size-1.5 rounded-full bg-emerald-400" />
                      Live CRM
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    AI-enriched prospects captured from target business directories
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {/* Priority Filter Pill */}
                  <div className="flex rounded-lg border border-white/[0.08] bg-white/[0.02] p-0.5 text-xs">
                    {(['All', 'High', 'Medium', 'Low'] as const).map((p) => (
                      <button
                        key={p}
                        onClick={() => setPriorityFilter(p)}
                        className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                          priorityFilter === p
                            ? 'bg-emerald-400/20 text-emerald-300'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {p}
                      </button>
                    ))}
                  </div>

                  {/* Sort Order Toggle */}
                  <Button
                    variant="outline"
                    onClick={() => setSortDescending(!sortDescending)}
                    className="h-8 gap-2 border-white/[0.1] bg-transparent text-xs text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"
                  >
                    <Clock3 className="size-3.5" />
                    {sortDescending ? 'Recent first' : 'Oldest first'}
                  </Button>
                </div>
              </div>

              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-white/[0.07] hover:bg-transparent">
                        <TableHead className="whitespace-nowrap px-5 py-3 text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600 sm:px-6">
                          Captured
                        </TableHead>
                        <TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                          Company
                        </TableHead>
                        <TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                          Email
                        </TableHead>
                        <TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                          Priority
                        </TableHead>
                        <TableHead className="min-w-[340px] whitespace-nowrap pr-5 text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600 sm:pr-6">
                          AI analysis & Observable Signals
                        </TableHead>
                      </TableRow>
                    </TableHeader>

                    <TableBody>
                      {loading ? (
                        <TableRow>
                          <TableCell colSpan={5} className="py-12 text-center text-xs text-slate-500">
                            <div className="flex items-center justify-center gap-2">
                              <Loader2 className="size-4 animate-spin text-emerald-400" />
                              <span>Loading live leads from Google Sheets...</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : processedLeads.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={5} className="py-12 text-center text-xs text-slate-500">
                            {searchQuery || priorityFilter !== 'All' ? (
                              <div>
                                <p>No leads matching current search/filter criteria.</p>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setSearchQuery('')
                                    setPriorityFilter('All')
                                  }}
                                  className="mt-2 text-xs text-emerald-300"
                                >
                                  Clear filters
                                </Button>
                              </div>
                            ) : (
                              <div>
                                <p>No leads recorded yet.</p>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={runAiScan}
                                  className="mt-3 border-emerald-400/20 bg-emerald-400/10 text-xs text-emerald-300 hover:bg-emerald-400/20"
                                >
                                  <Sparkles className="mr-1.5 size-3.5" /> Run first scan
                                </Button>
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ) : (
                        processedLeads.map((lead) => (
                          <TableRow
                            key={lead.id}
                            className="border-white/[0.06] transition-colors hover:bg-white/[0.025]"
                          >
                            <TableCell className="whitespace-nowrap px-5 py-4 text-xs text-slate-500 sm:px-6">
                              {lead.timestamp}
                            </TableCell>

                            <TableCell className="whitespace-nowrap">
                              <div className="flex items-center gap-3">
                                <div className="flex size-8 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-[10px] font-semibold text-slate-300">
                                  {lead.initials}
                                </div>
                                <div>
                                  <span className="text-sm font-medium text-slate-200">{lead.company}</span>
                                  {lead.website && (
                                    <p className="text-[11px] text-slate-500 hover:text-slate-400">
                                      <a href={lead.website} target="_blank" rel="noopener noreferrer">
                                        {lead.website.replace(/^https?:\/\//, '')}
                                      </a>
                                    </p>
                                  )}
                                </div>
                              </div>
                            </TableCell>

                            <TableCell className="whitespace-nowrap text-xs text-slate-400">
                              <span className="inline-flex items-center gap-2">
                                <Mail className="size-3.5 text-slate-600" />
                                {lead.email}
                              </span>
                            </TableCell>

                            <TableCell>
                              <Badge
                                className={
                                  lead.priority.toLowerCase() === 'high'
                                    ? 'border-emerald-400/20 bg-emerald-400 text-[10px] font-semibold text-[#07100d] hover:bg-emerald-400'
                                    : lead.priority.toLowerCase() === 'medium'
                                    ? 'border-violet-400/20 bg-violet-400/15 text-[10px] font-medium text-violet-300 hover:bg-violet-400/20'
                                    : 'border-white/[0.1] bg-white/[0.06] text-[10px] font-medium text-slate-400 hover:bg-white/[0.06]'
                                }
                              >
                                {lead.priority}
                              </Badge>
                            </TableCell>

                            <TableCell className="pr-5 text-xs leading-relaxed text-slate-400 sm:pr-6">
                              <span
                                className={`mr-2 inline-flex size-1.5 rounded-full align-middle ${
                                  lead.priority.toLowerCase() === 'high'
                                    ? 'bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.8)]'
                                    : 'bg-slate-500'
                                }`}
                              />
                              {lead.summary}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>

              <div className="flex items-center justify-between border-t border-white/[0.07] px-5 py-3 text-[11px] text-slate-600 sm:px-6">
                <span>
                  Showing {processedLeads.length} of {leads.length} leads
                  {priorityFilter !== 'All' && ` (${priorityFilter} priority only)`}
                </span>
                <span className="inline-flex items-center gap-2">
                  <Users className="size-3.5" />
                  CRM Sync Active
                </span>
              </div>
            </Card>
          </div>
        </section>
      </div>
    </main>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  accent,
  compact = false,
}: {
  icon: typeof Activity
  label: string
  value: string
  detail: string
  accent: 'emerald' | 'violet' | 'blue' | 'amber'
  compact?: boolean
}) {
  const iconStyles = {
    emerald: 'bg-emerald-400/10 text-emerald-300',
    violet: 'bg-violet-400/10 text-violet-300',
    blue: 'bg-sky-400/10 text-sky-300',
    amber: 'bg-amber-400/10 text-amber-300',
  }

  return (
    <Card className="border-white/[0.08] bg-[#0d1118] shadow-lg shadow-black/10">
      <CardContent className="relative overflow-hidden p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <p className={`mt-3 font-semibold tracking-[-0.03em] text-slate-50 ${compact ? 'text-lg' : 'text-[30px]'}`}>
              {value}
            </p>
            <p className="mt-1 text-[11px] text-slate-600">{detail}</p>
          </div>
          <div className={`flex size-9 items-center justify-center rounded-lg ${iconStyles[accent]}`}>
            <Icon className="size-[17px]" />
          </div>
        </div>
        <div
          className={`absolute -bottom-7 -right-5 size-24 rounded-full blur-3xl ${
            accent === 'emerald'
              ? 'bg-emerald-400/10'
              : accent === 'violet'
              ? 'bg-violet-400/10'
              : accent === 'blue'
              ? 'bg-sky-400/10'
              : 'bg-amber-400/10'
          }`}
        />
      </CardContent>
    </Card>
  )
}
