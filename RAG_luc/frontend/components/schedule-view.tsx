"use client"

import * as React from "react"
import { Calendar as CalendarIcon, Clock, BookOpen, ChevronRight, AlertCircle, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

interface CardSRS {
  stability: number;    // FSRS: Stability (ngày)
  difficulty: number;   // FSRS: Difficulty (1-10)
  reps: number;         // Số lần ôn tập
  due_date: string | null;
  last_review: string | null;
}

interface Flashcard {
  id: string;
  question: string;
  answer: string;
  srs?: CardSRS;
}

interface FlashcardSet {
  id: string;
  title: string;
  name: string;
  cards: Flashcard[];
  created_at: string;
}

export function ScheduleView({ onStudy }: { onStudy: (set: any) => void }) {
  const [sets, setSets] = React.useState<FlashcardSet[]>([])
  const [isLoading, setIsLoading] = React.useState(true)

  React.useEffect(() => {
    fetchSets()
  }, [])

  const fetchSets = async () => {
    try {
      const response = await fetch("/api/library")
      if (response.ok) {
        const data = await response.json()
        setSets(data.sets || [])
      } else {
        toast.error("Không thể tải lịch học")
      }
    } catch (error) {
      console.error("Fetch schedule error:", error)
      toast.error("Lỗi kết nối server")
    } finally {
      setIsLoading(false)
    }
  }

  const getScheduleData = () => {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    const nextWeek = new Date(today)
    nextWeek.setDate(nextWeek.getDate() + 7)

    const schedule = {
      overdue: [] as { set: FlashcardSet; cards: Flashcard[] }[],
      today: [] as { set: FlashcardSet; cards: Flashcard[] }[],
      tomorrow: [] as { set: FlashcardSet; cards: Flashcard[] }[],
      upcoming: [] as { set: FlashcardSet; cards: Flashcard[] }[],
    }

    sets.forEach(set => {
      const cardsOverdue: Flashcard[] = []
      const cardsToday: Flashcard[] = []
      const cardsTomorrow: Flashcard[] = []
      const cardsUpcoming: Flashcard[] = []

      set.cards.forEach(card => {
        if (!card.srs?.due_date) {
          cardsToday.push(card)
          return
        }

        const dueDate = new Date(card.srs.due_date)
        const dueDay = new Date(dueDate.getFullYear(), dueDate.getMonth(), dueDate.getDate())

        if (dueDate < now) {
          cardsOverdue.push(card)
        } else if (dueDay.getTime() === today.getTime()) {
          cardsToday.push(card)
        } else if (dueDay.getTime() === tomorrow.getTime()) {
          cardsTomorrow.push(card)
        } else if (dueDate <= nextWeek) {
          cardsUpcoming.push(card)
        }
      })

      if (cardsOverdue.length > 0) schedule.overdue.push({ set, cards: cardsOverdue })
      if (cardsToday.length > 0) schedule.today.push({ set, cards: cardsToday })
      if (cardsTomorrow.length > 0) schedule.tomorrow.push({ set, cards: cardsTomorrow })
      if (cardsUpcoming.length > 0) schedule.upcoming.push({ set, cards: cardsUpcoming })
    })

    return schedule
  }

  const schedule = getScheduleData()
  const totalDueToday = schedule.overdue.reduce((acc, i) => acc + i.cards.length, 0) + 
                        schedule.today.reduce((acc, i) => acc + i.cards.length, 0)

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Đang tính toán lịch học...</p>
      </div>
    )
  }

  const renderSection = (title: string, items: { set: FlashcardSet; cards: Flashcard[] }[], color: string, description: string) => {
    if (items.length === 0) return null
    return (
      <div className="space-y-4 pt-4">
        <div className="flex items-center gap-3">
          <div className={cn("w-1 h-6 rounded-full", color)} />
          <div>
            <h3 className="text-lg font-bold tracking-tight">{title}</h3>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </div>
        <div className="grid gap-4">
          {items.map(({ set, cards }) => (
            <Card key={`${title}-${set.id}`} className="group hover:border-primary/50 transition-colors bg-white/50 backdrop-blur-sm">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div className="space-y-1">
                  <CardTitle className="text-lg font-bold">{set.name || set.title}</CardTitle>
                  <CardDescription className="flex items-center gap-2">
                    <BookOpen className="w-3.5 h-3.5" />
                    {set.cards.length} thẻ tổng cộng
                  </CardDescription>
                </div>
                <Badge variant="secondary" className="bg-primary/5 text-primary border-none px-3 py-1">
                  {cards.length} thẻ
                </Badge>
              </CardHeader>
              <CardContent className="pt-2">
                <div className="flex items-center justify-between">
                  <div className="flex gap-4 text-[10px] text-muted-foreground uppercase font-bold tracking-widest">
                    {title === 'Quá hạn' ? '⚠️ Cần học ngay' : '📅 Theo kế hoạch'}
                  </div>
                  <Button 
                    onClick={() => onStudy({ ...set, cards, isEarly: title === 'Ngày mai' || title === '7 ngày tới' })}
                    size="sm"
                    className="gap-2 rounded-full px-5 h-9 font-bold transition-all"
                  >
                    Học tập
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-10">
      <div className="flex flex-col gap-2">
        <h2 className="text-4xl font-black tracking-tighter">Lộ Trình Học Tập</h2>
        <p className="text-muted-foreground">
          {totalDueToday > 0 
            ? `Bạn có ${totalDueToday} thẻ cần tập trung giải quyết trong hôm nay.`
            : "Hôm nay bạn đã hoàn thành xuất sắc, hãy xem lịch trình các ngày tới."}
        </p>
      </div>

      <div className="space-y-10">
        {renderSection("Quá hạn", schedule.overdue, "bg-red-500", "Những thẻ bạn đã lỡ nhịp, cần cứu vãn ngay!")}
        {renderSection("Hôm nay", schedule.today, "bg-primary", "Đúng kế hoạch, hãy duy trì phong độ.")}
        {renderSection("Ngày mai", schedule.tomorrow, "bg-orange-500", "Chuẩn bị tinh thần cho ngày mới.")}
        {renderSection("7 ngày tới", schedule.upcoming, "bg-blue-500", "Cái nhìn tổng quan về lộ trình dài hơi.")}

        {Object.values(schedule).every(arr => arr.length === 0) && (
          <Card className="border-dashed bg-muted/20">
            <CardContent className="flex flex-col items-center justify-center py-16 text-center space-y-4">
              <div className="w-20 h-20 bg-primary/5 rounded-full flex items-center justify-center">
                <CalendarIcon className="w-10 h-10 text-primary/40" />
              </div>
              <div className="space-y-2">
                <h3 className="font-bold text-2xl">Lịch trình trống</h3>
                <p className="text-sm text-muted-foreground max-w-sm">
                  Bạn chưa có thẻ nào được lập lịch. Hãy tạo thêm bộ thẻ mới từ PDF hoặc tài liệu để bắt đầu!
                </p>
              </div>
              <Button variant="outline" className="rounded-full mt-4" onClick={() => window.location.reload()}>
                Làm mới dữ liệu
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Spaced Repetition Info */}
      <Card className="bg-muted/30 border-none">
        <CardContent className="p-6 flex gap-4">
          <div className="bg-blue-500/10 p-3 rounded-xl h-fit">
            <AlertCircle className="w-5 h-5 text-blue-500" />
          </div>
          <div className="space-y-1">
            <h4 className="font-semibold text-sm">Về thuật toán lặp lại ngắt quãng</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Chúng tôi sử dụng thuật toán <strong>FSRS v4</strong> (Free Spaced Repetition Scheduler) để tối ưu hóa việc ghi nhớ của bạn.
              Hệ thống tính toán <em>Stability</em> và <em>Retrievability</em> của từng thẻ để xác định đúng thời điểm ôn tập, giúp bạn nhớ lâu hơn với ít nỗ lực nhất.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
