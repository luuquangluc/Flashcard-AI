"use client"

import * as React from "react"
import { RadarChart } from "./radar-chart"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Zap, Trophy, Target, Flame, BookOpen, TrendingUp,
  Award, Star, ShieldCheck, Brain, CheckCircle2, Clock,
  BarChart3, Layers, Lock
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

// ── Mini bar chart (Lịch sử tạo thẻ theo ngày) ─────────────────────────
function MiniBarChart({ data }: { data: { date: string; count: number }[] }) {
  const max = Math.max(...data.map(d => d.count), 1)
  return (
    <div className="flex items-end gap-1.5 h-20 w-full">
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1 group">
          <div
            className="w-full rounded-t-md bg-primary/80 hover:bg-primary transition-all duration-300 relative"
            style={{ height: `${Math.max((d.count / max) * 100, 4)}%` }}
          >
            <span className="absolute -top-6 left-1/2 -translate-x-1/2 text-[9px] font-bold text-primary opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
              {d.count} thẻ
            </span>
          </div>
          <span className="text-[8px] text-muted-foreground">{d.date}</span>
        </div>
      ))}
    </div>
  )
}

// ── Huy hiệu định nghĩa ─────────────────────────────────────────────────
const BADGE_DEFS = [
  {
    id: "first_card",
    name: "Người Tiền Trạm",
    icon: ShieldCheck,
    desc: "Tạo 10 thẻ đầu tiên",
    color: "text-blue-500",
    bg: "bg-blue-50",
    check: (stats: any, totalCards: number) => totalCards >= 10,
  },
  {
    id: "speed_demon",
    name: "Kẻ Hủy Diệt",
    icon: Zap,
    desc: "Ôn tập 50 thẻ/ngày",
    color: "text-yellow-500",
    bg: "bg-yellow-50",
    check: (stats: any) => (stats?.xp || 0) >= 500,
  },
  {
    id: "streak7",
    name: "Bền Bỉ",
    icon: Flame,
    desc: "Chuỗi 7 ngày học",
    color: "text-orange-500",
    bg: "bg-orange-50",
    check: (stats: any) => (stats?.streak || 0) >= 7,
  },
  {
    id: "expert",
    name: "Chuyên Gia",
    icon: Target,
    desc: "Đạt Level 5+",
    color: "text-purple-500",
    bg: "bg-purple-50",
    check: (stats: any) => (stats?.level || 1) >= 5,
  },
  {
    id: "library",
    name: "Nhà Sưu Tập",
    icon: Layers,
    desc: "Có 5 bộ thẻ trong thư viện",
    color: "text-green-500",
    bg: "bg-green-50",
    check: (stats: any, totalCards: number, setCount: number) => setCount >= 5,
  },
  {
    id: "master",
    name: "Bậc Thầy",
    icon: Brain,
    desc: "Thành thạo 50 thẻ",
    color: "text-indigo-500",
    bg: "bg-indigo-50",
    check: (stats: any, totalCards: number, setCount: number, masterCards: number) => masterCards >= 50,
  },
  {
    id: "consistent",
    name: "Kiên Định",
    icon: TrendingUp,
    desc: "Chuỗi 30 ngày học",
    color: "text-teal-500",
    bg: "bg-teal-50",
    check: (stats: any) => (stats?.streak || 0) >= 30,
  },
  {
    id: "legend",
    name: "Huyền Thoại",
    icon: Trophy,
    desc: "Đạt Level 10+",
    color: "text-amber-500",
    bg: "bg-amber-50",
    check: (stats: any) => (stats?.level || 1) >= 10,
  },
]

// ── Mức XP cần để lên level ──────────────────────────────────────────────
const XP_PER_LEVEL = 1000

export function AnalyticsView() {
  const [stats, setStats] = React.useState<any>(null)
  const [libraryData, setLibraryData] = React.useState<any[]>([])
  const [history, setHistory] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, libRes, historyRes] = await Promise.all([
          fetch("/api/stats"),
          fetch("/api/library"),
          fetch("/api/analytics")
        ])
        if (statsRes.ok && libRes.ok && historyRes.ok) {
          const s = await statsRes.json()
          const l = await libRes.json()
          const h = await historyRes.json()
          setStats(s.stats)
          setLibraryData(l.sets || [])
          setHistory(h.history || [])
        }
      } catch (err) {
        toast.error("Lỗi khi tải dữ liệu thống kê")
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
        <div className="flex flex-col md:flex-row gap-8">
          <div className="flex-1 h-[400px] bg-muted rounded-[2rem]" />
          <div className="flex-1 h-[400px] bg-muted rounded-[2rem]" />
        </div>
      </div>
    )
  }

  // ── Tính toán số liệu theo FSRS ──────────────────────────────────────────
  const now = new Date()
  const totalCards = libraryData.reduce((acc, set) => acc + (set.cards?.length || 0), 0)
  const setCount = libraryData.length

  const reviewedCards = libraryData.reduce((acc, set) =>
    acc + (set.cards?.filter((c: any) => (c.srs?.reps || 0) > 0).length || 0), 0)

  // FSRS: Tính retrievability = (1 + elapsed_days / (9 * stability))^-1
  // Thành thạo = stability > 21 ngày (nhớ được lâu dài)
  const masterCards = libraryData.reduce((acc, set) =>
    acc + (set.cards?.filter((c: any) => (c.srs?.stability || 0) > 21).length || 0), 0)

  // FSRS: Cần ôn = retrievability < 0.9 HOẶC chưa học
  const dueCards = libraryData.reduce((acc, set) =>
    acc + (set.cards?.filter((c: any) => {
      if (!c.srs?.due_date) return true  // Chưa học lần nào
      return new Date(c.srs.due_date) <= now  // Đã đến hạn
    }).length || 0), 0)

  // FSRS: Tính trung bình Retrievability thực tế của toàn bộ thẻ đã học
  const allReviewedCards = libraryData.flatMap(set =>
    (set.cards || []).filter((c: any) => (c.srs?.stability || 0) > 0)
  )
  const avgRetrievability = allReviewedCards.length > 0
    ? allReviewedCards.reduce((acc: number, c: any) => {
        const stability = c.srs?.stability || 1
        const dueDate = c.srs?.due_date ? new Date(c.srs.due_date) : now
        const elapsedDays = Math.max(0, (now.getTime() - dueDate.getTime()) / 86400000)
        const r = Math.pow(1 + elapsedDays / (9 * stability), -1)
        return acc + Math.min(r, 1)
      }, 0) / allReviewedCards.length
    : 0

  // FSRS: Trung bình Difficulty (1-10, thấp hơn = dễ hơn)
  const avgDifficulty = allReviewedCards.length > 0
    ? allReviewedCards.reduce((acc: number, c: any) => acc + (c.srs?.difficulty || 5), 0) / allReviewedCards.length
    : 5

  const avgAccuracy = history.length > 0
    ? history.reduce((acc, sess) => acc + (sess.level_stats?.accuracy || 0), 0) / history.length
    : 0

  const totalCardsGenerated = history.reduce((acc, sess) => acc + (sess.card_count || 0), 0)

  // XP Progress
  const currentXP = stats?.xp || 0
  const currentLevel = stats?.level || 1
  const xpInCurrentLevel = currentXP % XP_PER_LEVEL
  const xpProgress = (xpInCurrentLevel / XP_PER_LEVEL) * 100

  // ── Radar Chart — dùng chỉ số FSRS thực ──────────────────────────────────
  // Ghi nhớ = trung bình Retrievability thực tế (0-100%)
  const memoryScore = avgRetrievability * 100
  // Kiên trì = streak * 10 (tối đa 100)
  const persistenceScore = Math.min((stats?.streak || 0) * 10, 100)
  // Chính xác = (10 - avgDifficulty) / 9 * 100 (difficulty thấp = chính xác cao)
  const accuracyScore = Math.min(((10 - avgDifficulty) / 9) * 100, 100)
  // Số lượng = tổng thẻ / 150
  const quantityScore = Math.min((totalCards / 150) * 100, 100)
  // Đa dạng = số bộ thẻ / 15
  const varietyScore = Math.min((setCount / 15) * 100, 100)

  const radarData = [
    { label: "Ghi nhớ", value: Math.max(memoryScore, 5), fullMark: 100 },
    { label: "Kiên trì", value: Math.max(persistenceScore, 5), fullMark: 100 },
    { label: "Chính xác", value: Math.max(accuracyScore, 5), fullMark: 100 },
    { label: "Số lượng", value: Math.max(quantityScore, 5), fullMark: 100 },
    { label: "Đa dạng", value: Math.max(varietyScore, 5), fullMark: 100 },
  ]

  // ── Mini Bar Chart — 14 ngày gần nhất ─────────────────────────────────
  const last14Days = Array.from({ length: 14 }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (13 - i))
    return d.toISOString().split("T")[0]
  })
  const historyByDay = last14Days.map(date => {
    const count = history.filter(h => h.created_at?.startsWith(date))
      .reduce((acc, h) => acc + (h.card_count || 0), 0)
    return {
      date: date.slice(5),    // MM-DD
      count
    }
  })

  // ── Summary cards ──────────────────────────────────────────────────────
  const summaryCards = [
    {
      label: "Tổng thẻ", value: totalCards,
      icon: BookOpen, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200"
    },
    {
      // FSRS: Thành thạo = stability > 21 ngày
      label: "Thành thạo (S>21)", value: masterCards,
      icon: CheckCircle2, color: "text-green-600", bg: "bg-green-50", border: "border-green-200"
    },
    {
      label: "Cần ôn tập", value: dueCards,
      icon: Clock, color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200"
    },
    {
      // FSRS: Hiển thị Retrievability trung bình
      label: "Khả năng nhớ", value: avgRetrievability > 0 ? `${(avgRetrievability * 100).toFixed(0)}%` : "—",
      icon: Brain, color: "text-indigo-600", bg: "bg-indigo-50", border: "border-indigo-200"
    },
  ]

  return (
    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">

      {/* ── 4 Số liệu nhanh ── */}
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

      {/* ── Radar + XP/Stats ── */}
      <div className="flex flex-col md:flex-row gap-8 items-start">

        {/* Radar Chart */}
        <Card className="flex-1 w-full border-none shadow-2xl shadow-primary/5 bg-gradient-to-br from-white to-secondary/30 rounded-[2.5rem] overflow-hidden">
          <CardHeader className="text-center pb-0 pt-10">
            <Badge className="w-fit mx-auto mb-3 bg-primary/10 text-primary hover:bg-primary/20 border-none px-4 py-1.5 text-xs font-bold uppercase tracking-wider">
              Chỉ số học tập
            </Badge>
            <CardTitle className="text-4xl font-black tracking-tighter text-zinc-900">ĐA GIÁC NĂNG LỰC</CardTitle>
            <CardDescription className="text-sm font-medium text-muted-foreground">
              Phân tích dựa trên {reviewedCards} lượt ôn tập thực tế
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center pb-10">
            <RadarChart data={radarData} size={340} />
          </CardContent>
        </Card>

        {/* XP + Streak */}
        <div className="w-full md:w-[380px] space-y-5">

          {/* Level Card */}
          <Card className="border-none shadow-xl bg-zinc-900 text-white rounded-[2.5rem] overflow-hidden relative group">
            <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:scale-110 transition-transform">
              <Trophy className="w-24 h-24" />
            </div>
            <CardContent className="p-8 space-y-4">
              <div className="flex items-center gap-3">
                <div className="bg-primary p-2 rounded-xl">
                  <Award className="w-5 h-5 text-zinc-900" />
                </div>
                <span className="text-sm font-bold uppercase tracking-widest text-primary">Cấp độ hiện tại</span>
              </div>
              <div className="space-y-1">
                <h3 className="text-5xl font-black italic">LEVEL {currentLevel}</h3>
                <p className="text-zinc-400 font-medium">
                  {currentLevel < 3 ? "Học viên sơ cấp" :
                    currentLevel < 5 ? "Học viên trung cấp" :
                    currentLevel < 8 ? "Học giả" : "Bậc thầy"}
                </p>
              </div>
              <div className="space-y-2 pt-2">
                <div className="flex justify-between text-xs font-bold uppercase tracking-tighter">
                  <span>{xpInCurrentLevel} XP</span>
                  <span className="text-primary">Lên cấp: {XP_PER_LEVEL} XP</span>
                </div>
                {avgDifficulty > 0 && (
                  <p className="text-[10px] text-zinc-500">
                    Độ khó trung bình FSRS: {avgDifficulty.toFixed(1)} / 10
                  </p>
                )}
                <Progress value={xpProgress} className="h-2.5 bg-white/10" />
                <p className="text-[10px] text-zinc-500">Tổng XP tích lũy: {currentXP}</p>
              </div>
            </CardContent>
          </Card>

          {/* Streak + Accuracy */}
          <div className="grid grid-cols-2 gap-4">
            <Card className="border-none shadow-lg rounded-3xl bg-orange-500/10">
              <CardContent className="p-6 flex flex-col items-center gap-2">
                <Flame className="w-8 h-8 text-orange-500" />
                <span className="text-3xl font-black text-orange-600">{stats?.streak || 0}</span>
                <span className="text-[10px] font-bold uppercase text-orange-600/70 text-center">Ngày liên tiếp</span>
              </CardContent>
            </Card>
            <Card className="border-none shadow-lg rounded-3xl bg-green-500/10">
              <CardContent className="p-6 flex flex-col items-center gap-2">
                <Target className="w-8 h-8 text-green-500" />
                <span className="text-3xl font-black text-green-600">
                  {avgRetrievability > 0 ? `${(avgRetrievability * 100).toFixed(0)}%` : "—"}
                </span>
                <span className="text-[10px] font-bold uppercase text-green-600/70 text-center">Khả năng nhớ (FSRS)</span>
              </CardContent>
            </Card>
          </div>

          {/* Tỉ lệ thành thạo */}
          <Card className="border-none shadow-lg rounded-3xl">
            <CardContent className="p-6 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-zinc-700 flex items-center gap-2">
                  <Brain className="w-4 h-4 text-indigo-500" /> Tỉ lệ thành thạo (FSRS)
                </span>
                <span className="text-sm font-black text-indigo-600">
                  {totalCards > 0 ? `${((masterCards / totalCards) * 100).toFixed(0)}%` : "0%"}
                </span>
              </div>
              <Progress
                value={totalCards > 0 ? (masterCards / totalCards) * 100 : 0}
                className="h-3 bg-indigo-100"
              />
              <p className="text-[10px] text-muted-foreground">{masterCards} / {totalCards} thẻ có Stability &gt; 21 ngày</p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── Biểu đồ lịch sử 14 ngày ── */}
      <Card className="border-none shadow-xl rounded-[2.5rem] overflow-hidden">
        <CardHeader className="pb-2 pt-8 px-8">
          <div className="flex items-center gap-3">
            <div className="bg-primary/10 p-2 rounded-xl">
              <BarChart3 className="w-5 h-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-xl font-black">Lịch sử tạo thẻ</CardTitle>
              <CardDescription>Số thẻ AI đã tạo trong 14 ngày gần nhất</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-8 pb-8 pt-6">
          {history.length > 0 ? (
            <MiniBarChart data={historyByDay} />
          ) : (
            <div className="flex flex-col items-center justify-center h-20 text-muted-foreground gap-2">
              <BarChart3 className="w-8 h-8 opacity-20" />
              <p className="text-sm">Chưa có dữ liệu lịch sử</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Huy hiệu động ── */}
      <section className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="bg-primary/10 p-2 rounded-xl">
            <Star className="w-5 h-5 text-primary" />
          </div>
          <h3 className="text-2xl font-black">Huy hiệu thành tích</h3>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {BADGE_DEFS.map((badge) => {
            const earned = badge.check(stats, totalCards, setCount, masterCards)
            return (
              <Card
                key={badge.id}
                className={cn(
                  "border-none shadow-md rounded-[2rem] transition-all duration-300",
                  earned ? "hover:scale-105 cursor-pointer" : "opacity-50 grayscale"
                )}
              >
                <CardContent className="p-6 flex flex-col items-center text-center gap-3">
                  <div className={cn("p-4 rounded-full relative", badge.bg)}>
                    <badge.icon className={cn("w-8 h-8", badge.color)} />
                    {!earned && (
                      <div className="absolute inset-0 rounded-full bg-zinc-200/60 flex items-center justify-center">
                        <Lock className="w-4 h-4 text-zinc-500" />
                      </div>
                    )}
                  </div>
                  <div>
                    <h4 className="font-bold text-zinc-900">{badge.name}</h4>
                    <p className="text-[10px] text-muted-foreground font-medium mt-0.5">{badge.desc}</p>
                  </div>
                  {earned && (
                    <Badge className="bg-green-100 text-green-700 border-none text-[9px] font-bold uppercase tracking-wider">
                      ✓ Đã đạt
                    </Badge>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      </section>

    </div>
  )
}
