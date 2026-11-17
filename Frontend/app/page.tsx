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
  Compass,
  ExternalLink,
  FileText,
  Filter,
  Globe,
  Globe2,
  LayoutDashboard,
  Loader2,
  Mail,
  MapPin,
  Menu,
  Phone,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
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
  country: string
  city: string
  industry: string
  website: string
  email: string
  phone: string
  websiteStatus: 'working' | 'broken' | 'missing' | 'unverified' | string
  opportunityType: string
  priority: 'High' | 'Medium' | 'Low' | 'Unscored' | string
  summary: string
  evidence: string
  sourceUrl: string
  discoveryProvider: string
  initials: string
}

interface DiscoverySummary {
  total_discovered: number
  with_website_count: number
  without_website_count: number
  high_priority_count: number
  duplicates_skipped: number
  crm_synced: number
  stage?: string
  query?: {
    country: string
    city: string
    industry: string
    limit: number
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const TARGET_COUNTRIES = ['USA', 'UK', 'Australia', 'UAE', 'Canada', 'Germany']
const COMMON_INDUSTRIES = [
  'Restaurants',
  'Salons',
  'Dentists',
  'Healthcare',
  'Fitness',
  'Logistics',
  'Bakeries',
  'Law Firms',
  'Real Estate',
]

export default function Page() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'Overview' | 'Lead Feed' | 'AI Insights' | 'Discovery'>('Overview')
  
  // Data state
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [discoveryResults, setDiscoveryResults] = useState<LeadItem[]>([])
  const [viewSource, setViewSource] = useState<'crm' | 'discovery'>('crm')
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState<string | null>(null)
  const [agentModel, setAgentModel] = useState<string>('Gemini Flash')
  const [lastSyncTime, setLastSyncTime] = useState<string>('Never')

  // Search, filter & sort state
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [priorityFilter, setPriorityFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All')
  const [opportunityFilter, setOpportunityFilter] = useState<string>('All')
  const [sortDescending, setSortDescending] = useState(true)

  // Discovery Form State
  const [discCountry, setDiscCountry] = useState('USA')
  const [discCity, setDiscCity] = useState('New York')
  const [discIndustry, setDiscIndustry] = useState('Restaurants')
  const [discLimit, setDiscLimit] = useState(20)
  const [isDiscovering, setIsDiscovering] = useState(false)
  const [discoveryStage, setDiscoveryStage] = useState<string | null>(null)
  const [lastDiscoverySummary, setLastDiscoverySummary] = useState<DiscoverySummary | null>(null)

  // URL Scan state (preserved)
  const [isScanning, setIsScanning] = useState(false)
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'info' | 'error' } | null>(null)

  // Normalize raw record into LeadItem
  const normalizeLead = (record: RawLeadRecord, index: number): LeadItem => {
   const rawCompany =
  record['Business Name'] ||
  record['Company Name'] ||
  record.business_name ||
  record.company_name ||
  record.company ||
  'Unknown Prospect'

const company =
  typeof rawCompany === 'string'
    ? rawCompany
    : typeof rawCompany === 'number'
      ? String(rawCompany)
      : 'Unknown Prospect'
      
    const timestamp =
      record['Timestamp (UTC)'] || record.timestamp || record['Discovery Date'] || record.Captured || 'Recently'
    const country = record.Country || record.country || 'Global'
    const city = record.City || record.city || ''
    const industry = record.Industry || record.industry || record['Business Category'] || record.business_category || 'Business'
    const website = record.Website || record.website || ''
    const email = record.Email || record.email || ''
    const phone = record.Phone || record.phone || ''
    const websiteStatus = record['Website Status'] || record.website_status || (website ? 'working' : 'missing')
    const opportunityType = record['Opportunity Type'] || record.opportunity_type || 'General Automation'
    const priority = record.Priority || record.priority || 'Medium'
    const summary =
      record['AI Reasoning'] || record.Reason || record.reason || record.summary || record.description || 'No analysis recorded.'
    const evidence = record.Evidence || record.evidence || ''
    const sourceUrl = record['Source URL'] || record.source_url || ''
    const discoveryProvider = record['Discovery Provider'] || record.discovery_provider || 'openstreetmap_overpass'

    const initials =
      company
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map((w: string) => w[0])
        .join('')
        .toUpperCase() || 'CO'

    return {
      id: `${company}-${city}-${index}`,
      timestamp,
      company,
      country,
      city,
      industry,
      website,
      email,
      phone,
      websiteStatus,
      opportunityType,
      priority,
      summary,
      evidence,
      sourceUrl,
      discoveryProvider,
      initials,
    }
  }

  // Fetch leads from backend CRM
  const fetchLeads = useCallback(async () => {
    try {
      setLoading(true)
      setApiError(null)

      try {
        const healthRes = await fetch(`${API_BASE}/health`)
        if (healthRes.ok) {
          const healthData = await healthRes.json()
          if (healthData.integrations?.gemini?.model) {
            setAgentModel(healthData.integrations.gemini.model)
          }
        }
      } catch {
        // metadata fetch non-blocking
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

  // Start Autonomous Business Discovery (Phase 5)
  const startAutonomousDiscovery = async () => {
    if (isDiscovering) return
    setIsDiscovering(true)
    setDiscoveryStage('Querying OpenStreetMap Provider...')
    setNotification({
      message: `Searching for ${discIndustry} in ${discCity}, ${discCountry}...`,
      type: 'info',
    })

    try {
      const res = await fetch(`${API_BASE}/api/discovery/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          country: discCountry,
          city: discCity,
          industry: discIndustry,
          limit: Number(discLimit),
        }),
      })

      if (!res.ok) {
        const errJson = await res.json().catch(() => null)
        throw new Error(errJson?.detail?.error || 'Discovery start request failed.')
      }

      // Poll discovery status
      let pollCount = 0
      const poll = setInterval(async () => {
        pollCount += 1
        try {
          const statusRes = await fetch(`${API_BASE}/api/discovery/status`)
          if (statusRes.ok) {
            const statusData = await statusRes.json()
            const stage = statusData.summary?.stage
            if (stage === 'querying_provider') {
              setDiscoveryStage('Querying OpenStreetMap Provider...')
            } else if (stage === 'auditing_websites') {
              setDiscoveryStage('Deep Crawling & Technical Website Auditing...')
            } else if (stage === 'ai_qualification') {
              setDiscoveryStage('Gemini AI Opportunity Qualification...')
            } else if (stage === 'crm_sync') {
              setDiscoveryStage('Google Sheets CRM Sync & Deduplication...')
            }

            if (statusData.status === 'complete') {
              clearInterval(poll)
              setIsDiscovering(false)
              setDiscoveryStage(null)
              const sum = statusData.summary || {}
              setLastDiscoverySummary(sum)

              // Fetch latest discovery results
              const resultsRes = await fetch(`${API_BASE}/api/discovery/results`)
              if (resultsRes.ok) {
                const resultsData = await resultsRes.json()
                const recs = (resultsData.results || []).map((r: any, i: number) => normalizeLead(r, i))
                setDiscoveryResults(recs)
                setViewSource('discovery')
              }

              setNotification({
                message: `Discovery complete! Found ${sum.total_discovered} real businesses (${sum.high_priority_count} High Priority). Saved ${sum.crm_synced} to CRM (${sum.duplicates_skipped} duplicates skipped).`,
                type: 'success',
              })

              fetchLeads()
            } else if (statusData.status === 'error') {
              clearInterval(poll)
              setIsDiscovering(false)
              setDiscoveryStage(null)
              setNotification({
                message: `Discovery failed: ${statusData.error || 'Provider timeout'}`,
                type: 'error',
              })
            }
          }
        } catch {
          // ignore transient poll error
        }

        if (pollCount > 40) {
          clearInterval(poll)
          setIsDiscovering(false)
          setDiscoveryStage(null)
          setNotification({ message: 'Discovery request still processing in background. Refreshing...', type: 'info' })
          fetchLeads()
        }
      }, 2000)
    } catch (err: any) {
      setIsDiscovering(false)
      setDiscoveryStage(null)
      setNotification({ message: err.message || 'Failed to start discovery.', type: 'error' })
    }
  }

  // Trigger legacy URL AI Scan
  const runAiScan = async () => {
    if (isScanning) return
    setIsScanning(true)
    setNotification({ message: 'Initiating directory scraper & AI scoring...', type: 'info' })

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
              setNotification({
                message: `Scan complete! Scraped ${sum.scraped || 0} leads, identified ${sum.high || 0} High priority.`,
                type: 'success',
              })
              fetchLeads()
            } else if (statusData.status === 'error') {
              clearInterval(pollInterval)
              setIsScanning(false)
              setNotification({
                message: `Scan error: ${statusData.error || 'Pipeline failed'}`,
                type: 'error',
              })
            }
          }
        } catch {
          // ignore
        }

        if (attempts > 30) {
          clearInterval(pollInterval)
          setIsScanning(false)
          fetchLeads()
        }
      }, 1500)
    } catch (err: any) {
      setIsScanning(false)
      setNotification({ message: err.message || 'Failed to trigger scan.', type: 'error' })
    }
  }

  // Active dataset according to view mode
  const activeDataset = viewSource === 'discovery' && discoveryResults.length > 0 ? discoveryResults : leads

  // Filtered and sorted leads
  const processedLeads = useMemo(() => {
    let result = [...activeDataset]

    // Sidebar Tab filter
    if (activeTab === 'AI Insights') {
      result = result.filter((l) => l.priority.toLowerCase() === 'high')
    }

    // Priority filter
    if (priorityFilter !== 'All') {
      result = result.filter((l) => l.priority.toLowerCase() === priorityFilter.toLowerCase())
    }

    // Opportunity type filter
    if (opportunityFilter !== 'All') {
      result = result.filter((l) => l.opportunityType.toLowerCase() === opportunityFilter.toLowerCase())
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      result = result.filter(
        (l) =>
          l.company.toLowerCase().includes(q) ||
          l.city.toLowerCase().includes(q) ||
          l.country.toLowerCase().includes(q) ||
          l.industry.toLowerCase().includes(q) ||
          l.email.toLowerCase().includes(q) ||
          l.phone.toLowerCase().includes(q) ||
          l.summary.toLowerCase().includes(q) ||
          l.opportunityType.toLowerCase().includes(q) ||
          l.website.toLowerCase().includes(q)
      )
    }

    // Sort order
    result.sort((a, b) => {
      const cmp = a.timestamp.localeCompare(b.timestamp)
      return sortDescending ? -cmp : cmp
    })

    return result
  }, [activeDataset, activeTab, priorityFilter, opportunityFilter, searchQuery, sortDescending])

  // Dynamic metrics calculations
  const totalCount = leads.length
  const highPriorityCount = leads.filter((l) => l.priority.toLowerCase() === 'high').length
  const highPercentage = totalCount > 0 ? Math.round((highPriorityCount / totalCount) * 100) : 0
  const websitesFoundCount = leads.filter((l) => l.website && l.websiteStatus !== 'missing').length
  const websitesMissingCount = leads.filter((l) => !l.website || l.websiteStatus === 'missing').length

  const navItems = [
    { label: 'Overview' as const, icon: LayoutDashboard },
    { label: 'Lead Feed' as const, icon: Target },
    { label: 'AI Insights' as const, icon: Sparkles },
    { label: 'Discovery' as const, icon: Compass },
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
              <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Autonomous Discovery</p>
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
                  {item.label === 'Discovery' && isDiscovering && (
                    <span className="ml-auto size-2 rounded-full bg-amber-400 animate-ping" />
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
              Refresh CRM
            </Button>
            <Button
              variant="ghost"
              onClick={() => setPriorityFilter(priorityFilter === 'High' ? 'All' : 'High')}
              className="justify-start gap-3 rounded-lg px-3 text-[13px] font-medium text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"
            >
              <Filter className="size-[17px]" />
              Priority: {priorityFilter}
            </Button>
          </div>

          <div className="mt-auto rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] p-3">
            <div className="flex items-center gap-2">
              <span
                className={`size-2 rounded-full ${
                  isDiscovering || isScanning
                    ? 'animate-pulse bg-amber-400 shadow-[0_0_10px_#fbbf24]'
                    : 'bg-emerald-400 shadow-[0_0_10px_#34d399]'
                }`}
              />
              <span className="text-xs font-medium text-emerald-300">
                {isDiscovering ? 'Discovery Active' : isScanning ? 'Scanner Active' : 'Autonomous Engine'}
              </span>
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
              {discoveryStage || 'OpenStreetMap Discovery & Gemini Intelligence ready.'}
            </p>
          </div>

          <div className="mt-5 flex items-center gap-3 border-t border-white/[0.07] px-2 pt-4">
            <div className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 text-[11px] font-bold">
              SA
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">Saurabh Gupta</p>
              <p className="truncate text-[10px] text-slate-500">Growth Architect</p>
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
                <p className="text-xs text-slate-500">Autonomous B2B Discovery Platform</p>
                <h1 className="mt-0.5 text-lg font-semibold tracking-tight text-slate-50">
                  Lead Engine <span className="text-slate-500">/</span> {activeTab}
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
                    placeholder="Search by company, city, opportunity..."
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

              {/* Legacy Quick URL Scan */}
              <Button
                onClick={runAiScan}
                disabled={isScanning || isDiscovering}
                variant="outline"
                className="hidden h-9 gap-1.5 border-white/[0.1] bg-transparent text-xs text-slate-300 hover:bg-white/[0.05] sm:flex"
              >
                {isScanning ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5 text-violet-400" />}
                URL Scan
              </Button>
            </div>
          </header>

          <div className="mx-auto max-w-[1440px] px-5 py-7 sm:px-8 lg:py-9">
            {/* Notification Banner */}
            {notification && (
              <div
                className={`mb-6 flex items-center justify-between rounded-lg border px-4 py-3 text-xs ${
                  notification.type === 'success'
                    ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                    : notification.type === 'error'
                    ? 'border-red-400/20 bg-red-400/10 text-red-300'
                    : 'border-blue-400/20 bg-blue-400/10 text-blue-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  {notification.type === 'success' ? (
                    <CheckCircle2 className="size-4" />
                  ) : (
                    <AlertCircle className="size-4" />
                  )}
                  <span>{notification.message}</span>
                </div>
                <button
                  onClick={() => setNotification(null)}
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
                    Backend communication note: {apiError}. Ensure FastAPI is running on port 8000.
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

            {/* Autonomous Discovery Controller Card */}
            <Card className="mb-8 border-white/[0.08] bg-[#0d1118] p-5 shadow-xl">
              <div className="flex flex-col gap-4">
                <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
                  <div className="flex items-center gap-2.5">
                    <div className="flex size-7 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-400">
                      <Compass className="size-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-slate-100">
                        Autonomous Business Discovery & Audit Engine
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        Discover genuine businesses from OpenStreetMap, conduct security & website audits, and qualify opportunities with Gemini
                      </p>
                    </div>
                  </div>

                  {discoveryStage && (
                    <div className="flex items-center gap-2 rounded-md bg-amber-400/10 px-3 py-1.5 text-xs text-amber-300 border border-amber-400/20">
                      <Loader2 className="size-3.5 animate-spin" />
                      <span>{discoveryStage}</span>
                    </div>
                  )}
                </div>

                {/* Form Controls */}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-5 items-end">
                  {/* Country Selector */}
                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-[0.15em] text-slate-500 mb-1.5">
                      Target Country
                    </label>
                    <select
                      value={discCountry}
                      onChange={(e) => setDiscCountry(e.target.value)}
                      disabled={isDiscovering}
                      className="h-9 w-full rounded-lg border border-white/[0.1] bg-[#121822] px-3 text-xs text-slate-200 focus:border-emerald-400 focus:outline-none"
                    >
                      {TARGET_COUNTRIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* City Input */}
                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-[0.15em] text-slate-500 mb-1.5">
                      City / Metro
                    </label>
                    <input
                      type="text"
                      value={discCity}
                      onChange={(e) => setDiscCity(e.target.value)}
                      disabled={isDiscovering}
                      placeholder="e.g. New York, London"
                      className="h-9 w-full rounded-lg border border-white/[0.1] bg-[#121822] px-3 text-xs text-slate-200 focus:border-emerald-400 focus:outline-none"
                    />
                  </div>

                  {/* Industry Input / Selector */}
                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-[0.15em] text-slate-500 mb-1.5">
                      Industry / Niche
                    </label>
                    <select
                      value={discIndustry}
                      onChange={(e) => setDiscIndustry(e.target.value)}
                      disabled={isDiscovering}
                      className="h-9 w-full rounded-lg border border-white/[0.1] bg-[#121822] px-3 text-xs text-slate-200 focus:border-emerald-400 focus:outline-none"
                    >
                      {COMMON_INDUSTRIES.map((ind) => (
                        <option key={ind} value={ind}>
                          {ind}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Max Results */}
                  <div>
                    <label className="block text-[10px] font-medium uppercase tracking-[0.15em] text-slate-500 mb-1.5">
                      Max Results (1-100)
                    </label>
                    <input
                      type="number"
                      min={5}
                      max={100}
                      value={discLimit}
                      onChange={(e) => setDiscLimit(Number(e.target.value))}
                      disabled={isDiscovering}
                      className="h-9 w-full rounded-lg border border-white/[0.1] bg-[#121822] px-3 text-xs text-slate-200 focus:border-emerald-400 focus:outline-none"
                    />
                  </div>

                  {/* Trigger Button */}
                  <div>
                    <Button
                      onClick={startAutonomousDiscovery}
                      disabled={isDiscovering}
                      className="h-9 w-full gap-2 rounded-lg bg-emerald-400 text-xs font-semibold text-[#07100d] hover:bg-emerald-300 disabled:opacity-50"
                    >
                      {isDiscovering ? (
                        <>
                          <Loader2 className="size-3.5 animate-spin" />
                          Discovering...
                        </>
                      ) : (
                        <>
                          <Compass className="size-3.5" />
                          Start Discovery
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                {/* Latest Discovery Stats Summary */}
                {lastDiscoverySummary && (
                  <div className="mt-2 flex flex-wrap items-center gap-4 rounded-lg border border-white/[0.05] bg-white/[0.02] px-4 py-2 text-[11px] text-slate-400">
                    <span className="text-slate-200 font-medium">Session Output:</span>
                    <span>Discovered: <strong className="text-white">{lastDiscoverySummary.total_discovered}</strong></span>
                    <span>Websites Audited: <strong className="text-emerald-300">{lastDiscoverySummary.with_website_count}</strong></span>
                    <span>No Website: <strong className="text-amber-300">{lastDiscoverySummary.without_website_count}</strong></span>
                    <span>High Fit Opportunities: <strong className="text-violet-300">{lastDiscoverySummary.high_priority_count}</strong></span>
                    <span>Duplicates Skipped: <strong className="text-sky-300">{lastDiscoverySummary.duplicates_skipped}</strong></span>
                    <span>CRM Appended: <strong className="text-white">{lastDiscoverySummary.crm_synced}</strong></span>
                  </div>
                )}
              </div>
            </Card>

            {/* Dynamic Metric Cards */}
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                icon={FileText}
                label="Total in CRM"
                value={String(totalCount)}
                detail="verified business prospects"
                accent="emerald"
              />
              <MetricCard
                icon={Target}
                label="High Priority Fit"
                value={String(highPriorityCount)}
                detail={`${highPercentage}% qualified opportunities`}
                accent="violet"
              />
              <MetricCard
                icon={Globe2}
                label="Web Presence Ratio"
                value={totalCount > 0 ? `${Math.round((websitesFoundCount / totalCount) * 100)}%` : '0%'}
                detail={`${websitesFoundCount} with site · ${websitesMissingCount} missing`}
                accent="blue"
              />
              <MetricCard
                icon={Bot}
                label="AI Qualification Model"
                value={agentModel.replace('models/', '')}
                detail="OpenStreetMap + Gemini"
                accent="amber"
                compact
              />
            </div>

            {/* Live Lead Table Card */}
            <Card className="mt-6 overflow-hidden border-white/[0.08] bg-[#0d1118] shadow-2xl shadow-black/10">
              <div className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-100">
                      {viewSource === 'discovery' ? 'Latest Discovery Session' : 'Google Sheets Live CRM Feed'}
                    </h3>
                    <Badge className="border-emerald-400/20 bg-emerald-400/10 text-[10px] font-medium text-emerald-300">
                      <span className="mr-1 size-1.5 rounded-full bg-emerald-400" />
                      Live Verified
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {viewSource === 'discovery'
                      ? 'Results from the most recent autonomous web discovery run'
                      : 'Persistent CRM records synchronized with your Google Sheet'}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {/* View Mode Toggle */}
                  {discoveryResults.length > 0 && (
                    <div className="flex rounded-lg border border-white/[0.08] bg-white/[0.02] p-0.5 text-xs mr-2">
                      <button
                        onClick={() => setViewSource('crm')}
                        className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                          viewSource === 'crm'
                            ? 'bg-emerald-400/20 text-emerald-300'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        All CRM Leads ({leads.length})
                      </button>
                      <button
                        onClick={() => setViewSource('discovery')}
                        className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                          viewSource === 'discovery'
                            ? 'bg-emerald-400/20 text-emerald-300'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Latest Batch ({discoveryResults.length})
                      </button>
                    </div>
                  )}

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
                          Business & Location
                        </TableHead>
                        <TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                          Website & Audit
                        </TableHead>
                        <TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                          Contact Info
                        </TableHead>
                        <TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                          Priority & Opportunity
                        </TableHead>
                        <TableHead className="min-w-[340px] whitespace-nowrap pr-5 text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600 sm:pr-6">
                          AI Reasoning & Technical Evidence
                        </TableHead>
                        <TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">
                          Source
                        </TableHead>
                      </TableRow>
                    </TableHeader>

                    <TableBody>
                      {loading ? (
                        <TableRow>
                          <TableCell colSpan={6} className="py-12 text-center text-xs text-slate-500">
                            <div className="flex items-center justify-center gap-2">
                              <Loader2 className="size-4 animate-spin text-emerald-400" />
                              <span>Loading live verified leads...</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : processedLeads.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="py-12 text-center text-xs text-slate-500">
                            <div>
                              <p>No leads matching current search/filter criteria.</p>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={startAutonomousDiscovery}
                                className="mt-3 border-emerald-400/20 bg-emerald-400/10 text-xs text-emerald-300 hover:bg-emerald-400/20"
                              >
                                <Compass className="mr-1.5 size-3.5" /> Start new discovery
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : (
                        processedLeads.map((lead) => (
                          <TableRow
                            key={lead.id}
                            className="border-white/[0.06] transition-colors hover:bg-white/[0.025]"
                          >
                            {/* Business & Location */}
                            <TableCell className="whitespace-nowrap px-5 py-4 sm:px-6">
                              <div className="flex items-center gap-3">
                                <div className="flex size-8 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-[10px] font-semibold text-slate-300">
                                  {lead.initials}
                                </div>
                                <div>
                                  <span className="text-sm font-medium text-slate-200">{lead.company}</span>
                                  <p className="flex items-center gap-1 text-[11px] text-slate-500">
                                    <MapPin className="size-3 text-slate-600" />
                                    {lead.city ? `${lead.city}, ` : ''}{lead.country} · <span className="text-slate-400">{lead.industry}</span>
                                  </p>
                                </div>
                              </div>
                            </TableCell>

                            {/* Website & Audit status */}
                            <TableCell className="whitespace-nowrap text-xs">
                              {lead.website ? (
                                <div className="flex flex-col gap-1">
                                  <a
                                    href={lead.website}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-emerald-300 hover:underline max-w-[180px] truncate"
                                  >
                                    <Globe className="size-3 shrink-0" />
                                    {lead.website.replace(/^https?:\/\/(www\.)?/, '')}
                                    <ExternalLink className="size-2.5 opacity-60" />
                                  </a>
                                  <span
                                    className={`inline-flex items-center gap-1 w-fit rounded px-1.5 py-0.5 text-[9px] font-medium uppercase ${
                                      lead.websiteStatus === 'working'
                                        ? 'bg-emerald-400/10 text-emerald-400 border border-emerald-400/20'
                                        : lead.websiteStatus === 'broken'
                                        ? 'bg-red-400/10 text-red-400 border border-red-400/20'
                                        : 'bg-slate-400/10 text-slate-400'
                                    }`}
                                  >
                                    {lead.websiteStatus}
                                  </span>
                                </div>
                              ) : (
                                <span className="inline-flex items-center gap-1 rounded bg-amber-400/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300 border border-amber-400/20">
                                  No Website
                                </span>
                              )}
                            </TableCell>

                            {/* Contact Info */}
                            <TableCell className="whitespace-nowrap text-xs text-slate-400">
                              <div className="flex flex-col gap-1">
                                {lead.phone && (
                                  <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-300">
                                    <Phone className="size-3 text-slate-500" />
                                    {lead.phone}
                                  </span>
                                )}
                                {lead.email && (
                                  <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-400 truncate max-w-[160px]">
                                    <Mail className="size-3 text-slate-500" />
                                    {lead.email}
                                  </span>
                                )}
                                {!lead.phone && !lead.email && (
                                  <span className="text-[10px] text-slate-600">Via Directory</span>
                                )}
                              </div>
                            </TableCell>

                            {/* Priority & Opportunity Type */}
                            <TableCell className="whitespace-nowrap">
                              <div className="flex flex-col gap-1">
                                <Badge
                                  className={
                                    lead.priority.toLowerCase() === 'high'
                                      ? 'border-emerald-400/20 bg-emerald-400 text-[10px] font-semibold text-[#07100d]'
                                      : lead.priority.toLowerCase() === 'medium'
                                      ? 'border-violet-400/20 bg-violet-400/15 text-[10px] font-medium text-violet-300'
                                      : 'border-white/[0.1] bg-white/[0.06] text-[10px] font-medium text-slate-400'
                                  }
                                >
                                  {lead.priority} Priority
                                </Badge>
                                <span className="text-[10px] font-medium text-slate-400">
                                  Opp: <strong className="text-slate-200">{lead.opportunityType}</strong>
                                </span>
                              </div>
                            </TableCell>

                            {/* AI Reasoning & Evidence */}
                            <TableCell className="pr-5 text-xs leading-relaxed text-slate-400 sm:pr-6 max-w-[360px]">
                              <p className="line-clamp-2">{lead.summary}</p>
                              {lead.evidence && (
                                <p className="mt-1 text-[10px] text-slate-500 truncate">
                                  <span className="text-slate-400">Signals:</span> {lead.evidence}
                                </p>
                              )}
                            </TableCell>

                            {/* Source Attribution Link */}
                            <TableCell className="whitespace-nowrap text-xs">
                              {lead.sourceUrl ? (
                                <a
                                  href={lead.sourceUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300"
                                >
                                  <span>OSM</span>
                                  <ExternalLink className="size-2.5" />
                                </a>
                              ) : (
                                <span className="text-[10px] text-slate-600">Local</span>
                              )}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>

              <div className="flex flex-col gap-2 border-t border-white/[0.07] px-5 py-3 text-[11px] text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                <span>
                  Showing {processedLeads.length} of {activeDataset.length} leads
                  {priorityFilter !== 'All' && ` (${priorityFilter} priority)`}
                </span>
                <div className="flex items-center gap-4 text-[11px]">
                  <span className="inline-flex items-center gap-1.5 text-slate-400">
                    <ShieldCheck className="size-3.5 text-emerald-400" />
                    Autonomous Web Intelligence
                  </span>
                  <span className="text-slate-600">|</span>
                  <span>
                    Map data ©{' '}
                    <a
                      href="https://www.openstreetmap.org/copyright"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-400 underline decoration-slate-600 underline-offset-2 hover:text-emerald-400"
                    >
                      OpenStreetMap contributors
                    </a>{' '}
                    (ODbL)
                  </span>
                </div>
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
