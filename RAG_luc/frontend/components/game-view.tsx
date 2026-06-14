"use client"

import * as React from "react"
import { 
  Timer, 
  Trophy, 
  RotateCcw, 
  ChevronLeft, 
  Zap,
  Star,
  Brain
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

interface GameViewProps {
  set: any
  onFinish: () => void
}

interface GameCard {
  id: string
  content: string
  matchId: string
  type: 'question' | 'answer'
}

export function GameView({ set, onFinish }: GameViewProps) {
  const [gameCards, setGameCards] = React.useState<GameCard[]>([])
  const [selectedIds, setSelectedIds] = React.useState<number[]>([])
  const [matchedIds, setMatchedIds] = React.useState<string[]>([])
  const [time, setTime] = React.useState(0)
  const [isGameStarted, setIsGameStarted] = React.useState(false)
  const [isGameFinished, setIsGameFinished] = React.useState(false)
  const [score, setScore] = React.useState(0)

  const timerRef = React.useRef<NodeJS.Timeout | null>(null)

  const initGame = React.useCallback(() => {
    const cards = set.cards || []
    // Lấy tối đa 6 thẻ để chơi (tổng 12 ô)
    const gamePool = [...cards].sort(() => 0.5 - Math.random()).slice(0, 6)
    
    let items: GameCard[] = []
    gamePool.forEach(card => {
      const matchId = card.id || Math.random().toString()
      items.push({ id: `q-${matchId}`, content: card.question, matchId, type: 'question' })
      items.push({ id: `a-${matchId}`, content: card.answer, matchId, type: 'answer' })
    })

    setGameCards(items.sort(() => 0.5 - Math.random()))
    setMatchedIds([])
    setSelectedIds([])
    setTime(0)
    setScore(0)
    setIsGameStarted(true)
    setIsGameFinished(false)

    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setTime(prev => prev + 1)
    }, 1000)
  }, [set])

  React.useEffect(() => {
    initGame()
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [initGame])

  const handleCardClick = (index: number) => {
    if (selectedIds.includes(index) || matchedIds.includes(gameCards[index].matchId)) return
    if (selectedIds.length === 2) return

    const newSelected = [...selectedIds, index]
    setSelectedIds(newSelected)

    if (newSelected.length === 2) {
      const first = gameCards[newSelected[0]]
      const second = gameCards[newSelected[1]]

      if (first.matchId === second.matchId && first.type !== second.type) {
        // Match!
        setMatchedIds(prev => [...prev, first.matchId])
        setSelectedIds([])
        setScore(prev => prev + 100)
        
        if (matchedIds.length + 1 === gameCards.length / 2) {
          // Win!
          finishGame()
        }
      } else {
        // No match
        setScore(prev => Math.max(0, prev - 20))
        setTimeout(() => setSelectedIds([]), 800)
      }
    }
  }

  const finishGame = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setIsGameFinished(true)
    toast.success("Tuyệt vời! Bạn đã hoàn thành trò chơi.")
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (isGameFinished) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-8 animate-in zoom-in-95">
         <div className="relative">
            <div className="absolute inset-0 bg-yellow-400/20 blur-3xl rounded-full animate-pulse" />
            <div className="relative bg-white p-10 rounded-full shadow-2xl border-4 border-yellow-100">
               <Trophy className="w-24 h-24 text-yellow-500 animate-bounce" />
            </div>
            <div className="absolute -top-2 -right-2 bg-zinc-900 text-white rounded-full p-2">
               <Star className="w-6 h-6 fill-current" />
            </div>
         </div>

         <div className="text-center space-y-2">
            <h2 className="text-5xl font-black tracking-tighter">VICTORY!</h2>
            <p className="text-muted-foreground text-xl">Bạn đã chinh phục bộ thẻ trong <strong>{formatTime(time)}</strong></p>
         </div>

         <div className="grid grid-cols-2 gap-8 w-full max-w-md">
            <div className="text-center p-6 bg-zinc-50 rounded-3xl border-2 border-zinc-100">
               <p className="text-[10px] font-black uppercase text-zinc-400 tracking-widest mb-2">Thời gian</p>
               <p className="text-3xl font-black text-zinc-900">{formatTime(time)}</p>
            </div>
            <div className="text-center p-6 bg-primary/5 rounded-3xl border-2 border-primary/10">
               <p className="text-[10px] font-black uppercase text-primary tracking-widest mb-2">Điểm số</p>
               <p className="text-3xl font-black text-primary">{score}</p>
            </div>
         </div>

         <div className="flex gap-4">
            <Button variant="outline" onClick={initGame} className="rounded-full px-10 h-14 font-bold border-2">
               <RotateCcw className="w-5 h-5 mr-2" /> Chơi lại
            </Button>
            <Button onClick={onFinish} className="rounded-full px-10 h-14 font-bold shadow-lg">
               Quay lại Thư viện
            </Button>
         </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between px-4">
         <Button variant="ghost" size="sm" onClick={onFinish} className="gap-2 rounded-full">
            <ChevronLeft className="w-4 h-4" /> Thoát game
         </Button>
         <div className="flex items-center gap-6 bg-zinc-900 text-white px-6 py-2 rounded-full shadow-lg">
            <div className="flex items-center gap-2">
               <Timer className="w-3.5 h-3.5 text-primary" />
               <span className="font-mono text-lg font-bold">{formatTime(time)}</span>
            </div>
            <div className="h-4 w-[1px] bg-white/20" />
            <div className="flex items-center gap-2">
               <Zap className="w-3.5 h-3.5 text-yellow-400" />
               <span className="font-bold text-lg">{score}</span>
            </div>
         </div>
         <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-zinc-400" />
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Matching Game</span>
         </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
         {gameCards.map((card, index) => {
           const isSelected = selectedIds.includes(index)
           const isMatched = matchedIds.includes(card.matchId)
           
           return (
             <Card 
               key={card.id}
               className={cn(
                 "h-28 flex items-center justify-center p-3 text-center cursor-pointer transition-all duration-300 rounded-2xl border-2 select-none",
                 isSelected ? "bg-primary text-white border-primary shadow-xl scale-105" : "bg-white border-zinc-100 hover:border-primary/50 hover:shadow-md",
                 isMatched ? "opacity-0 pointer-events-none scale-50" : "opacity-100"
               )}
               onClick={() => handleCardClick(index)}
             >
                <p className={cn(
                  "text-[13px] font-semibold leading-tight px-2",
                  isSelected ? "text-white" : "text-zinc-700"
                )}>
                  {card.content}
                </p>
             </Card>
           )
         })}
      </div>

      <div className="text-center pt-8">
         <p className="text-xs text-muted-foreground uppercase tracking-widest font-medium">
            Mẹo: Chọn Câu hỏi và Câu trả lời tương ứng để ghi điểm!
         </p>
      </div>
    </div>
  )
}
