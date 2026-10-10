'use client'

import {
  Activity,
  Bell,
  Bot,
  Building2,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileText,
  LayoutDashboard,
  Mail,
  Menu,
  Search,
  Settings2,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const leads = [
  {
    timestamp: 'Oct 10, 2026 · 09:42 AM',
    company: 'Northstar Logistics Inc',
    email: 'ops@northstarlogistics.com',
    priority: 'High',
    summary: 'Rapidly expanding delivery network. Strong fit for AI route optimization; estimated 30% efficiency upside.',
    initials: 'NL',
  },
  {
    timestamp: 'Oct 10, 2026 · 09:39 AM',
    company: 'Maple Cafe',
    email: 'hello@maplecafe.co',
    priority: 'Low',
    summary: 'Local hospitality business with a limited digital footprint. Nurture with a lightweight loyalty campaign.',
    initials: 'MC',
  },
  {
    timestamp: 'Oct 10, 2026 · 09:36 AM',
    company: 'Apex Dental Group',
    email: 'growth@apexdental.com',
    priority: 'High',
    summary: 'Multi-location practice actively hiring. High intent for patient acquisition and automated appointment flows.',
    initials: 'AD',
  },
  {
    timestamp: 'Oct 10, 2026 · 09:31 AM',
    company: 'BrightPath Tutoring',
    email: 'team@brightpathtutoring.com',
    priority: 'High',
    summary: 'Growing education brand with strong parent demand. Ideal for local SEO and conversion-focused landing pages.',
    initials: 'BT',
  },
  {
    timestamp: 'Oct 10, 2026 · 09:27 AM',
    company: 'Harborline Manufacturing',
    email: 'sales@harborlinemfg.com',
    priority: 'High',
    summary: 'Industrial supplier signals expansion into new territories. Prioritize for account-based outbound sequences.',
    initials: 'HM',
  },
]

const navItems = [
  { label: 'Overview', icon: LayoutDashboard, active: true },
  { label: 'Lead Feed', icon: Target },
  { label: 'AI Insights', icon: Sparkles },
  { label: 'Campaigns', icon: TrendingUp },
]

export default function Page() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <main className="min-h-screen bg-[#080b10] text-slate-100">
      <div className="flex min-h-screen">
        <aside className={`fixed inset-y-0 left-0 z-30 flex w-[250px] flex-col border-r border-white/[0.07] bg-[#0d1118] px-4 py-5 transition-transform duration-200 lg:static lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
          <div className="flex items-center gap-3 px-3">
            <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-400 text-[#07100d] shadow-[0_0_24px_rgba(52,211,153,0.24)]"><Zap className="size-[18px] fill-current" /></div>
            <div><p className="text-[14px] font-semibold tracking-tight">Lead Engine</p><p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">AI-powered growth</p></div>
          </div>

          <div className="mt-10 flex flex-col gap-1">
            <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-600">Workspace</p>
            {navItems.map((item) => <Button key={item.label} variant="ghost" className={`justify-start gap-3 rounded-lg px-3 text-[13px] font-medium ${item.active ? 'bg-emerald-400/[0.12] text-emerald-300 hover:bg-emerald-400/[0.16] hover:text-emerald-200' : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-100'}`}><item.icon className="size-[17px]" />{item.label}{item.label === 'Lead Feed' && <span className="ml-auto rounded-full bg-emerald-400/15 px-2 py-0.5 text-[10px] text-emerald-300">5</span>}</Button>)}
          </div>
          <div className="mt-8 flex flex-col gap-1">
            <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-600">Manage</p>
            <Button variant="ghost" className="justify-start gap-3 rounded-lg px-3 text-[13px] font-medium text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"><Settings2 className="size-[17px]" />Settings</Button>
            <Button variant="ghost" className="justify-start gap-3 rounded-lg px-3 text-[13px] font-medium text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"><CircleHelp className="size-[17px]" />Help center</Button>
          </div>
          <div className="mt-auto rounded-xl border border-emerald-400/15 bg-emerald-400/[0.06] p-3"><div className="flex items-center gap-2"><span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_10px_#34d399]" /><span className="text-xs font-medium text-emerald-300">Agent is active</span></div><p className="mt-2 text-[11px] leading-relaxed text-slate-500">Scanning 12 sources for high-intent prospects.</p></div>
          <div className="mt-5 flex items-center gap-3 border-t border-white/[0.07] px-2 pt-4"><div className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 text-[11px] font-bold">JD</div><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium">Jordan Davis</p><p className="truncate text-[10px] text-slate-500">Growth team</p></div><ChevronDown className="size-4 text-slate-600" /></div>
        </aside>

        <section className="min-w-0 flex-1">
          <header className="flex h-[72px] items-center justify-between border-b border-white/[0.07] px-5 sm:px-8"><div className="flex items-center gap-3"><Button variant="ghost" size="icon" className="text-slate-400 lg:hidden" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle sidebar"><Menu /></Button><div><p className="text-xs text-slate-500">Friday, October 10, 2026</p><h1 className="mt-0.5 text-lg font-semibold tracking-tight text-slate-50">Good morning, Jordan <span className="text-slate-500">/</span> Overview</h1></div></div><div className="flex items-center gap-2"><Button variant="ghost" size="icon" className="text-slate-400 hover:text-slate-100" aria-label="Search"><Search /></Button><Button variant="ghost" size="icon" className="relative text-slate-400 hover:text-slate-100" aria-label="Notifications"><Bell /><span className="absolute right-2 top-2 size-1.5 rounded-full bg-emerald-400" /></Button><div className="ml-2 hidden h-6 w-px bg-white/[0.08] sm:block" /><Button className="ml-1 hidden h-9 gap-2 rounded-lg bg-emerald-400 px-3 text-xs font-semibold text-[#07100d] hover:bg-emerald-300 sm:flex"><Sparkles /> Run AI scan</Button></div></header>

          <div className="mx-auto max-w-[1440px] px-5 py-7 sm:px-8 lg:py-9">
            <div className="mb-7 flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300"><Activity className="size-3.5" /> Live intelligence</div><h2 className="text-2xl font-semibold tracking-[-0.03em] text-white sm:text-[28px]">Lead generation, on autopilot.</h2><p className="mt-1.5 text-sm text-slate-500">Your AI agent found 5 new opportunities worth following up on.</p></div><div className="flex items-center gap-2 text-xs text-slate-500"><span className="size-1.5 rounded-full bg-emerald-400" />Last synced 2 min ago</div></div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard icon={FileText} label="Total scraped" value="5" detail="leads this session" accent="emerald" />
              <MetricCard icon={Target} label="High priority" value="4" detail="80% of new leads" accent="violet" />
              <MetricCard icon={TrendingUp} label="Efficiency gain" value="90%" detail="vs. manual prospecting" accent="blue" />
              <MetricCard icon={Bot} label="Active AI agent" value="Gemini 3.5-Flash" detail="Running · 12 sources" accent="amber" compact />
            </div>

            <Card className="mt-6 overflow-hidden border-white/[0.08] bg-[#0d1118] shadow-2xl shadow-black/10">
              <div className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6"><div><div className="flex items-center gap-2"><h3 className="text-sm font-semibold text-slate-100">Live lead feed</h3><Badge className="border-emerald-400/20 bg-emerald-400/10 text-[10px] font-medium text-emerald-300 hover:bg-emerald-400/10"><span className="mr-1 size-1.5 rounded-full bg-emerald-400" />Live</Badge></div><p className="mt-1 text-xs text-slate-500">AI-enriched prospects captured by your agent</p></div><div className="flex items-center gap-2"><Button variant="outline" className="h-8 gap-2 border-white/[0.1] bg-transparent text-xs text-slate-400 hover:bg-white/[0.05] hover:text-slate-100"><Clock3 /> Recent first</Button><Button variant="outline" size="icon" className="size-8 border-white/[0.1] bg-transparent text-slate-400 hover:bg-white/[0.05] hover:text-slate-100" aria-label="Filter leads"><Settings2 /></Button></div></div>
              <CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow className="border-white/[0.07] hover:bg-transparent"><TableHead className="whitespace-nowrap px-5 py-3 text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600 sm:px-6">Captured</TableHead><TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">Company</TableHead><TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">Email</TableHead><TableHead className="whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600">Priority</TableHead><TableHead className="min-w-[320px] whitespace-nowrap pr-5 text-[10px] font-medium uppercase tracking-[0.15em] text-slate-600 sm:pr-6">AI analysis</TableHead></TableRow></TableHeader><TableBody>{leads.map((lead) => <TableRow key={lead.company} className="border-white/[0.06] transition-colors hover:bg-white/[0.025]"><TableCell className="whitespace-nowrap px-5 py-4 text-xs text-slate-500 sm:px-6">{lead.timestamp}</TableCell><TableCell className="whitespace-nowrap"><div className="flex items-center gap-3"><div className="flex size-8 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-[10px] font-semibold text-slate-300">{lead.initials}</div><span className="text-sm font-medium text-slate-200">{lead.company}</span></div></TableCell><TableCell className="whitespace-nowrap text-xs text-slate-400"><span className="inline-flex items-center gap-2"><Mail className="size-3.5 text-slate-600" />{lead.email}</span></TableCell><TableCell><Badge className={lead.priority === 'High' ? 'border-emerald-400/20 bg-emerald-400 text-[10px] font-semibold text-[#07100d] hover:bg-emerald-400' : 'border-white/[0.1] bg-white/[0.06] text-[10px] font-medium text-slate-400 hover:bg-white/[0.06]'}>{lead.priority}</Badge></TableCell><TableCell className="pr-5 text-xs leading-relaxed text-slate-400 sm:pr-6"><span className="mr-2 inline-flex size-1.5 rounded-full bg-violet-400 align-middle shadow-[0_0_8px_rgba(167,139,250,0.8)]" />{lead.summary}</TableCell></TableRow>)}</TableBody></Table></div></CardContent>
              <div className="flex items-center justify-between border-t border-white/[0.07] px-5 py-3 text-[11px] text-slate-600 sm:px-6"><span>Showing 5 of 5 leads</span><span className="inline-flex items-center gap-2"><Users className="size-3.5" />Enrichment complete</span></div>
            </Card>
          </div>
        </section>
      </div>
    </main>
  )
}

function MetricCard({ icon: Icon, label, value, detail, accent, compact = false }: { icon: typeof Activity; label: string; value: string; detail: string; accent: 'emerald' | 'violet' | 'blue' | 'amber'; compact?: boolean }) {
  const iconStyles = { emerald: 'bg-emerald-400/10 text-emerald-300', violet: 'bg-violet-400/10 text-violet-300', blue: 'bg-sky-400/10 text-sky-300', amber: 'bg-amber-400/10 text-amber-300' }
  return <Card className="border-white/[0.08] bg-[#0d1118] shadow-lg shadow-black/10"><CardContent className="relative overflow-hidden p-5"><div className="flex items-start justify-between"><div><p className="text-xs font-medium text-slate-500">{label}</p><p className={`mt-3 font-semibold tracking-[-0.03em] text-slate-50 ${compact ? 'text-lg' : 'text-[30px]'}`}>{value}</p><p className="mt-1 text-[11px] text-slate-600">{detail}</p></div><div className={`flex size-9 items-center justify-center rounded-lg ${iconStyles[accent]}`}><Icon className="size-[17px]" /></div></div><div className={`absolute -bottom-7 -right-5 size-24 rounded-full blur-3xl ${accent === 'emerald' ? 'bg-emerald-400/10' : accent === 'violet' ? 'bg-violet-400/10' : accent === 'blue' ? 'bg-sky-400/10' : 'bg-amber-400/10'}`} /></CardContent></Card>
}
