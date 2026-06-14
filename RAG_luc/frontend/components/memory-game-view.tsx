"use client"

import * as React from "react"
import {
  Timer,
  Trophy,
  RotateCcw,
  ChevronLeft,
  Zap,
  Star,
  Eye,
  HelpCircle,
  MessageSquare
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

interface MemoryGameViewProps {
  set: any
  onFinish: () => void
}

interface MemoryCard {
  id: string
  content: string
  matchId: string
  type: 'question' | 'answer'
}

export function MemoryGameView({ set, onFinish }: MemoryGameViewProps) {
  const [gameCards, setGameCards] = React.useState<MemoryCard[]>([])
  const [flippedIndices, setFlippedIndices] = React.useState<number[]>([])
  const [matchedIds, setMatchedIds] = React.useState<string[]>([])
  const [time, setTime] = React.useState(0)
  const [isGameFinished, setIsGameFinished] = React.useState(false)
  const [moves, setMoves] = React.useState(0)
  const [isLocked, setIsLocked] = React.useState(false)
  const [combo, setCombo] = React.useState(0)
  const [bestCombo, setBestCombo] = React.useState(0)
  const [score, setScore] = React.useState(0)

  const timerRef = React.useRef<NodeJS.Timeout | null>(null)

  const initGame = React.useCallback(() => {
    const cards = set.cards || []
    
    let items: MemoryCard[] = []
    cards.forEach((card: any) => {
      const matchId = card.id || Math.random().toString()
      // Cắt ngắn nội dung để vừa thẻ
      const q = card.question?.length > 80 ? card.question.slice(0, 77) + '...' : card.question
      const a = card.answer?.length > 80 ? card.answer.slice(0, 77) + '...' : card.answer
      items.push({ id: `q-${matchId}`, content: q, matchId, type: 'question' })
      items.push({ id: `a-${matchId}`, content: a, matchId, type: 'answer' })
    })

    // Xáo trộn Fisher-Yates
    for (let i = items.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [items[i], items[j]] = [items[j], items[i]]
    }

    setGameCards(items)
    setMatchedIds([])
    setFlippedIndices([])
    setTime(0)
    setMoves(0)
    setScore(0)
    setCombo(0)
    setBestCombo(0)
    setIsGameFinished(false)
    setIsLocked(false)

    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setTime(prev => prev + 1)
    }, 1000)
  }, [set])

  React.useEffect(() => {
    initGame()
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [initGame])

  const handleFlip = (index: number) => {
    if (isLocked) return
    if (flippedIndices.includes(index)) return
    if (matchedIds.includes(gameCards[index].matchId)) return

    const newFlipped = [...flippedIndices, index]
    setFlippedIndices(newFlipped)

    if (newFlipped.length === 2) {
      setMoves(prev => prev + 1)
      setIsLocked(true)

      const first = gameCards[newFlipped[0]]
      const second = gameCards[newFlipped[1]]

      if (first.matchId === second.matchId && first.type !== second.type) {
        // Match!
        const newCombo = combo + 1
        setCombo(newCombo)
        setBestCombo(prev => Math.max(prev, newCombo))
        
        // Điểm: base 100 + combo bonus
        const comboBonus = Math.min(newCombo * 25, 200)
        setScore(prev => prev + 100 + comboBonus)

        setTimeout(() => {
          setMatchedIds(prev => {
            const updated = [...prev, first.matchId]
            if (updated.length === gameCards.length / 2) {
              finishGame()
            }
            return updated
          })
          setFlippedIndices([])
          setIsLocked(false)
        }, 600)
      } else {
        // No match
        setCombo(0)
        setTimeout(() => {
          setFlippedIndices([])
          setIsLocked(false)
        }, 1000)
      }
    }
  }

  const finishGame = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    setIsGameFinished(true)
    toast.success("Xuất sắc! Bạn đã ghép hết tất cả thẻ!")
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const totalPairs = gameCards.length / 2
  const progress = totalPairs > 0 ? (matchedIds.length / totalPairs) * 100 : 0

  // Tính số cột dựa trên số thẻ
  const totalCards = gameCards.length
  const gridCols = totalCards <= 8 ? 4 : totalCards <= 12 ? 4 : totalCards <= 16 ? 4 : 6

  if (isGameFinished) {
    const stars = moves <= totalPairs * 1.5 ? 3 : moves <= totalPairs * 2.5 ? 2 : 1
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
            <h2 className="text-5xl font-black tracking-tighter">HOÀN THÀNH!</h2>
            <div className="flex items-center justify-center gap-1 mt-3">
              {[1, 2, 3].map(i => (
                <Star key={i} className={cn("w-8 h-8 transition-all", i <= stars ? "text-yellow-400 fill-yellow-400 scale-110" : "text-zinc-200")} />
              ))}
            </div>
         </div>

         <div className="grid grid-cols-3 gap-6 w-full max-w-lg">
            <div className="text-center p-5 bg-zinc-50 rounded-2xl border-2 border-zinc-100">
               <p className="text-[10px] font-black uppercase text-zinc-400 tracking-widest mb-1">Thời gian</p>
               <p className="text-2xl font-black text-zinc-900">{formatTime(time)}</p>
            </div>
            <div className="text-center p-5 bg-primary/5 rounded-2xl border-2 border-primary/10">
               <p className="text-[10px] font-black uppercase text-primary tracking-widest mb-1">Điểm</p>
               <p className="text-2xl font-black text-primary">{score}</p>
            </div>
            <div className="text-center p-5 bg-yellow-50 rounded-2xl border-2 border-yellow-100">
               <p className="text-[10px] font-black uppercase text-yellow-600 tracking-widest mb-1">Lượt</p>
               <p className="text-2xl font-black text-yellow-600">{moves}</p>
            </div>
         </div>

         <div className="flex gap-4">
            <Button variant="outline" onClick={initGame} className="rounded-full px-10 h-14 font-bold border-2">
               <RotateCcw className="w-5 h-5 mr-2" /> Chơi lại
            </Button>
            <Button onClick={onFinish} className="rounded-full px-10 h-14 font-bold shadow-lg">
               Quay lại
            </Button>
         </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between px-2">
         <Button variant="ghost" size="sm" onClick={onFinish} className="gap-2 rounded-full">
            <ChevronLeft className="w-4 h-4" /> Thoát
         </Button>
         <div className="flex items-center gap-5 bg-zinc-900 text-white px-6 py-2.5 rounded-full shadow-lg">
            <div className="flex items-center gap-2">
               <Timer className="w-3.5 h-3.5 text-blue-400" />
               <span className="font-mono text-lg font-bold">{formatTime(time)}</span>
            </div>
            <div className="h-4 w-[1px] bg-white/20" />
            <div className="flex items-center gap-2">
               <Zap className="w-3.5 h-3.5 text-yellow-400" />
               <span className="font-bold text-lg">{score}</span>
            </div>
            <div className="h-4 w-[1px] bg-white/20" />
            <div className="flex items-center gap-2">
               <Eye className="w-3.5 h-3.5 text-emerald-400" />
               <span className="font-bold text-lg">{moves}</span>
            </div>
         </div>
         <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Memory Game</span>
         </div>
      </div>

      {/* Progress bar */}
      <div className="px-2">
        <div className="h-2 bg-zinc-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary to-blue-500 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex justify-between mt-1.5">
          <span className="text-xs text-muted-foreground font-medium">{matchedIds.length}/{totalPairs} cặp</span>
          {combo > 1 && (
            <span className="text-xs font-black text-yellow-500 animate-pulse">🔥 Combo x{combo}</span>
          )}
        </div>
      </div>

      {/* Card grid */}
      <div
        className="grid gap-3 px-2"
        style={{ gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))` }}
      >
         {gameCards.map((card, index) => {
           const isFlipped = flippedIndices.includes(index)
           const isMatched = matchedIds.includes(card.matchId)
           const showFace = isFlipped || isMatched

           return (
             <div
                key={card.id}
                className={cn(
                  "relative cursor-pointer select-none",
                  "aspect-[3/4] min-h-[100px]",
                  isMatched && "pointer-events-none"
                )}
                style={{ perspective: '600px' }}
                onClick={() => handleFlip(index)}
             >
               <div
                 className={cn(
                   "absolute inset-0 transition-all duration-500",
                   "[transform-style:preserve-3d]",
                   showFace && "[transform:rotateY(180deg)]"
                 )}
               >
                 {/* Back (face-down) */}
                 <div className={cn(
                   "absolute inset-0 rounded-2xl flex items-center justify-center",
                   "[backface-visibility:hidden]",
                   "bg-gradient-to-br from-zinc-800 to-zinc-900 border-2 border-zinc-700",
                   "shadow-lg hover:shadow-xl hover:scale-[1.03] transition-all duration-200",
                   "active:scale-95"
                 )}>
                   <div className="text-center">
                     <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center mx-auto mb-2">
                       <HelpCircle className="w-5 h-5 text-white/50" />
                     </div>
                     <span className="text-[10px] font-bold text-white/30 uppercase tracking-widest">Lật thẻ</span>
                   </div>
                 </div>
                 
                 {/* Front (face-up) */}
                 <div className={cn(
                   "absolute inset-0 rounded-2xl flex flex-col items-center justify-center p-3",
                   "[backface-visibility:hidden] [transform:rotateY(180deg)]",
                   "border-2 shadow-lg",
                   card.type === 'question'
                     ? "bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200"
                     : "bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-200",
                   isMatched && "opacity-60 scale-95 ring-4 ring-green-300"
                 )}>
                   <div className={cn(
                     "text-[10px] font-black uppercase tracking-widest mb-2 px-3 py-1 rounded-full",
                     card.type === 'question'
                       ? "bg-blue-100 text-blue-600"
                       : "bg-emerald-100 text-emerald-600"
                   )}>
                     {card.type === 'question' ? (
                       <span className="flex items-center gap-1"><HelpCircle className="w-3 h-3" /> Câu hỏi</span>
                     ) : (
                       <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" /> Trả lời</span>
                     )}
                   </div>
                   <p className={cn(
                     "text-xs font-semibold leading-relaxed text-center",
                     card.type === 'question' ? "text-blue-900" : "text-emerald-900"
                   )}>
                     {card.content}
                   </p>
                 </div>
               </div>
             </div>
           )
         })}
      </div>

      <div className="text-center pt-4">
         <p className="text-xs text-muted-foreground uppercase tracking-widest font-medium">
            Lật 2 thẻ — Ghép Câu hỏi với Câu trả lời tương ứng!
         </p>
      </div>
    </div>
  )
}
