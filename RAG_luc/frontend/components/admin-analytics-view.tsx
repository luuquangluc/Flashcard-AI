"use client"

import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Users, Layers, CreditCard, Cpu, TrendingUp,
  BarChart3, Zap, ArrowUpRight, Clock, Activity,
  Loader2, ShieldCheck
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

function TokenBar({ label, input, output, cost, count }: { label: string; input: number; output: number; cost: number; count: number }) {
  const total = input + output
  const inputPct = total > 0 ? (input / total) * 100 : 50
  return (
    <div className="space-y-2 py-3 border-b border-zinc-100 last:border-0">
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-zinc-700">{label}</span>
        <div className="flex items-center gap-3">
          <Badge variant="secondary" className="text-[10px] font-bold">{count} calls</Badge>
          <span className="text-xs font-bold text-emerald-600">${cost.toFixed(4)}</span>
        </div>
      </div>
      <div className="h-3 bg-zinc-100 rounded-full overflow-hidden flex">
        <div className="bg-blue-500 h-full transition-all" style={{ width: `${inputPct}%` }} />
        <div className="bg-orange-400 h-full transition-all" style={{ width: `${100 - inputPct}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground font-medium">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Input: {(input / 1000).toFixed(1)}K
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-orange-400 inline-block" /> Output: {(output / 1000).toFixed(1)}K
        </span>
      </div>
    </div>
  )
}

export function AdminAnalyticsView() {
  const [data, setData] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("/api/admin/stats", { credentials: 'include' })
        if (res.status === 403) {
          toast.error("Bạn không có quyền admin")
          return
        }
        if (res.ok) {
          setData(await res.json())
        } else {
          const errData = await res.json().catch(() => ({}))
          toast.error(errData.error || `Lỗi server: ${res.status}`)
        }
      } catch (err) {
        toast.error("Lỗi khi tải dữ liệu admin")
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return (
      <div className="space-y-10 animate-pulse">
        <div className="h-10 w-1/4 bg-muted rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-32 bg-muted rounded-[2rem]" />)}
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <ShieldCheck className="w-16 h-16 text-red-300" />
        <p className="text-muted-foreground font-medium">Không có quyền truy cập</p>
      </div>
    )
  }

  const tokens = data.tokens || {}
  const featureEntries = Object.entries(tokens.by_feature || {}) as [string, any][]
  const modelEntries = Object.entries(tokens.by_model || {}) as [string, any][]

  // Sort features by cost descending
  featureEntries.sort((a, b) => b[1].cost - a[1].cost)

  const summaryCards = [
    { label: "Người dùng", value: data.total_users, icon: Users, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200" },
    { label: "Bộ thẻ", value: data.total_sets, icon: Layers, color: "text-purple-600", bg: "bg-purple-50", border: "border-purple-200" },
    { label: "Tổng thẻ", value: data.total_cards, icon: CreditCard, color: "text-green-600", bg: "bg-green-50", border: "border-green-200" },
    { label: "Chi phí API", value: `$${tokens.total_cost_usd?.toFixed(4) || '0'}`, icon: Zap, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200" },
  ]

  return (
    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="bg-red-100 p-2.5 rounded-xl">
          <ShieldCheck className="w-6 h-6 text-red-600" />
        </div>
        <div>
          <h2 className="text-3xl font-black tracking-tight">Admin Dashboard</h2>
          <p className="text-muted-foreground text-sm">Thống kê toàn hệ thống</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {summaryCards.map((sc, i) => (
          <Card key={i} className={cn("border rounded-[2rem] shadow-md", sc.border)}>
            <CardContent className="p-6 flex flex-col gap-3">
              <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", sc.bg)}>
                <sc.icon className={cn("w-5 h-5", sc.color)} />
              </div>
              <div>
                <p className={cn("text-3xl font-black", sc.color)}>{sc.value}</p>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{sc.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Token Stats */}
      <div className="grid md:grid-cols-2 gap-8">

        {/* By Feature */}
        <Card className="border-none shadow-xl rounded-[2.5rem] overflow-hidden">
          <CardHeader className="pb-2 pt-8 px-8">
            <div className="flex items-center gap-3">
              <div className="bg-blue-100 p-2 rounded-xl">
                <Cpu className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <CardTitle className="text-xl font-black">Token theo tính năng</CardTitle>
                <CardDescription>{tokens.total_entries || 0} API calls tổng cộng</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="px-8 pb-8">
            <div className="space-y-1 mt-4">
              <div className="flex justify-between text-xs font-bold text-zinc-500 uppercase tracking-widest pb-2 border-b border-zinc-200">
                <span>Tổng Input</span>
                <span>Tổng Output</span>
              </div>
              <div className="flex justify-between text-lg font-black py-2">
                <span className="text-blue-600">{((tokens.total_input || 0) / 1000).toFixed(1)}K</span>
                <span className="text-orange-500">{((tokens.total_output || 0) / 1000).toFixed(1)}K</span>
              </div>
            </div>
            <div className="mt-4 max-h-[400px] overflow-y-auto">
              {featureEntries.map(([name, stats]) => (
                <TokenBar key={name} label={name} input={stats.input} output={stats.output} cost={stats.cost} count={stats.count} />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* By Model */}
        <Card className="border-none shadow-xl rounded-[2.5rem] overflow-hidden">
          <CardHeader className="pb-2 pt-8 px-8">
            <div className="flex items-center gap-3">
              <div className="bg-purple-100 p-2 rounded-xl">
                <Activity className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <CardTitle className="text-xl font-black">Token theo model</CardTitle>
                <CardDescription>Phân bổ chi phí theo model AI</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="px-8 pb-8">
            <div className="mt-4">
              {modelEntries.map(([name, stats]) => (
                <TokenBar key={name} label={name} input={stats.input} output={stats.output} cost={stats.cost} count={stats.count} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Users */}
      <Card className="border-none shadow-xl rounded-[2.5rem] overflow-hidden">
        <CardHeader className="pb-2 pt-8 px-8">
          <div className="flex items-center gap-3">
            <div className="bg-amber-100 p-2 rounded-xl">
              <TrendingUp className="w-5 h-5 text-amber-600" />
            </div>
            <CardTitle className="text-xl font-black">Top Users</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          <div className="space-y-3 mt-4">
            {(data.top_users || []).map((u: any, i: number) => (
              <div key={u.user_id} className="flex items-center justify-between py-2 border-b border-zinc-100 last:border-0">
                <div className="flex items-center gap-3">
                  <span className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-sm font-black",
                    i === 0 ? "bg-amber-100 text-amber-700" :
                    i === 1 ? "bg-zinc-100 text-zinc-600" :
                    i === 2 ? "bg-orange-100 text-orange-600" :
                    "bg-zinc-50 text-zinc-400"
                  )}>
                    {i + 1}
                  </span>
                  <div>
                    <p className="text-sm font-bold text-zinc-800">{u.name || u.username}</p>
                    <p className="text-[10px] text-muted-foreground">@{u.username}</p>
                  </div>
                </div>
                <Badge variant="secondary" className="font-bold">{u.total_cards} thẻ</Badge>
              </div>
            ))}
            {(data.top_users || []).length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">Chưa có dữ liệu</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Recent API Calls */}
      <Card className="border-none shadow-xl rounded-[2.5rem] overflow-hidden">
        <CardHeader className="pb-2 pt-8 px-8">
          <div className="flex items-center gap-3">
            <div className="bg-zinc-100 p-2 rounded-xl">
              <Clock className="w-5 h-5 text-zinc-600" />
            </div>
            <div>
              <CardTitle className="text-xl font-black">API Calls gần đây</CardTitle>
              <CardDescription>20 lượt gọi API gần nhất</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-8 pb-8">
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-200 text-left">
                  <th className="py-2 font-bold text-zinc-500 uppercase tracking-widest">Thời gian</th>
                  <th className="py-2 font-bold text-zinc-500 uppercase tracking-widest">Tính năng</th>
                  <th className="py-2 font-bold text-zinc-500 uppercase tracking-widest">Model</th>
                  <th className="py-2 font-bold text-zinc-500 uppercase tracking-widest text-right">Input</th>
                  <th className="py-2 font-bold text-zinc-500 uppercase tracking-widest text-right">Output</th>
                  <th className="py-2 font-bold text-zinc-500 uppercase tracking-widest text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {(tokens.recent || []).slice().reverse().map((entry: any, i: number) => (
                  <tr key={i} className="border-b border-zinc-50 hover:bg-zinc-50 transition-colors">
                    <td className="py-2 text-muted-foreground font-mono">{entry.timestamp}</td>
                    <td className="py-2 font-semibold">{entry.feature}</td>
                    <td className="py-2"><Badge variant="outline" className="text-[10px]">{entry.model}</Badge></td>
                    <td className="py-2 text-right font-mono text-blue-600">{(entry.input_tokens || 0).toLocaleString()}</td>
                    <td className="py-2 text-right font-mono text-orange-500">{(entry.output_tokens || 0).toLocaleString()}</td>
                    <td className="py-2 text-right font-mono text-emerald-600">${(entry.cost_usd || 0).toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

    </div>
  )
}
