"use client"

import * as React from "react"
import { 
  Check, 
  ChevronLeft, 
  ChevronRight, 
  RotateCcw, 
  Trophy,
  Volume2,
  Clock,
  Sparkles,
  Zap,
  Loader2,
  Pencil,
  Trash2,
  StickyNote
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { FlashcardEditor } from "./flashcard-editor"

interface StudyViewProps {
  set: any
  onFinish: () => void
}

export function StudyView({ set, onFinish }: StudyViewProps) {
  const [cards, setCards] = React.useState<any[]>(set.cards || [])
  const [currentIndex, setCurrentIndex] = React.useState(0)
  const [isFlipped, setIsFlipped] = React.useState(false)
  const [results, setResults] = React.useState<any[]>([])
  const [isFinished, setIsFinished] = React.useState(false)
  const [isEditorOpen, setIsEditorOpen] = React.useState(false)
  const [showNote, setShowNote] = React.useState(false)
  const [isRating, setIsRating] = React.useState(false)

  const currentCard = cards[currentIndex]
  const progress = ((currentIndex + 1) / cards.length) * 100

  const handleUpdateCard = async (newQuestion: string, newAnswer: string, newNote: string) => {
    try {
      const res = await fetch("/api/flashcard/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          set_id: set.id,
          card_id: currentCard.id,
          question: newQuestion,
          answer: newAnswer,
          note: newNote
        })
      })
      if (!res.ok) throw new Error("Lỗi cập nhật thẻ")
      setCards(prev => prev.map(c => c.id === currentCard.id ? { ...c, question: newQuestion, answer: newAnswer, note: newNote } : c))
      setIsEditorOpen(false)
      toast.success("Đã cập nhật thẻ")
    } catch (err) {
      toast.error("Không thể cập nhật thẻ")
    }
  }

  const handleDeleteCard = async () => {
    if (!confirm("Bạn có chắc chắn muốn xóa thẻ này khỏi bộ thẻ?")) return

    try {
      const res = await fetch("/api/flashcard/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          set_id: set.id,
          card_id: currentCard.id
        })
      })
      if (!res.ok) throw new Error("Lỗi xóa thẻ")
      
      const newCards = cards.filter(c => c.id !== currentCard.id)
      setCards(newCards)
      
      if (newCards.length === 0) {
        setIsFinished(true)
      } else {
        // Nếu xóa thẻ cuối cùng, lùi index lại
        if (currentIndex >= newCards.length) {
          setCurrentIndex(newCards.length - 1)
        }
      }
      toast.success("Đã xóa thẻ")
    } catch (err) {
      toast.error("Không thể xóa thẻ")
    }
  }

  // --- Retry Queue: lưu review thất bại vào localStorage để không mất dữ liệu ---
  const PENDING_KEY = `pending_reviews_${set.id}`
  const [pendingCount, setPendingCount] = React.useState(0)

  const getPendingReviews = React.useCallback((): Array<{card_id: string, quality: number}> => {
    try {
      return JSON.parse(localStorage.getItem(PENDING_KEY) || '[]')
    } catch { return [] }
  }, [PENDING_KEY])

  const savePendingReview = React.useCallback((cardId: string, quality: number) => {
    const pending = getPendingReviews()
    // Tránh trùng lặp: chỉ giữ review mới nhất cho mỗi card
    const filtered = pending.filter(r => r.card_id !== cardId)
    filtered.push({ card_id: cardId, quality })
    localStorage.setItem(PENDING_KEY, JSON.stringify(filtered))
    setPendingCount(filtered.length)
  }, [PENDING_KEY, getPendingReviews])

  const removePendingReview = React.useCallback((cardId: string) => {
    const pending = getPendingReviews()
    const filtered = pending.filter(r => r.card_id !== cardId)
    localStorage.setItem(PENDING_KEY, JSON.stringify(filtered))
    setPendingCount(filtered.length)
  }, [PENDING_KEY, getPendingReviews])

  // Retry tất cả pending reviews qua batch API
  const flushPendingReviews = React.useCallback(async () => {
    const pending = getPendingReviews()
    if (pending.length === 0) return

    try {
      const res = await fetch("/api/review/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ set_id: set.id, reviews: pending })
      })
      if (res.ok) {
        localStorage.removeItem(PENDING_KEY)
        setPendingCount(0)
        console.log(`✅ Flushed ${pending.length} pending reviews`)
      }
    } catch (err) {
      console.warn("Flush pending reviews failed, will retry later:", err)
    }
  }, [PENDING_KEY, getPendingReviews, set.id])

  // Khi mount: đọc pending count + thử flush nếu có
  React.useEffect(() => {
    const pending = getPendingReviews()
    setPendingCount(pending.length)
    if (pending.length > 0) {
      flushPendingReviews()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRate = async (quality: number) => {
    // Chặn double-click
    if (isRating) return
    setIsRating(true)
    
    // Nếu là học sớm, chỉ lưu cục bộ và chuyển thẻ, không gọi API ngay
    if (set.isEarly) {
      setResults(prev => [...prev, { card_id: currentCard.id, quality }])
      if (currentIndex < cards.length - 1) {
        setIsFlipped(false)
        setShowNote(false)
        setCurrentIndex(prev => prev + 1)
      } else {
        setIsFinished(true)
      }
      setIsRating(false)
      return
    }

    // Optimistic UI: chuyển thẻ ngay, gọi API background
    const reviewCardId = currentCard.id
    setResults(prev => [...prev, { card: currentCard, quality }])

    if (currentIndex < cards.length - 1) {
      setIsFlipped(false)
      setShowNote(false)
      setCurrentIndex(prev => prev + 1)
    } else {
      setIsFinished(true)
    }

    // Gọi API background, nếu fail thì lưu vào localStorage để retry
    try {
      const res = await fetch("/api/review/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          set_id: set.id,
          card_id: reviewCardId,
          quality: quality
        })
      })

      if (res.ok) {
        // Thành công → xóa khỏi pending (nếu có từ lần retry trước)
        removePendingReview(reviewCardId)
      } else {
        // API trả lỗi → lưu vào pending queue
        savePendingReview(reviewCardId, quality)
        toast.warning("Đang lưu tạm, sẽ đồng bộ lại sau")
      }
    } catch (err) {
      // Mất mạng / timeout → lưu vào pending queue
      savePendingReview(reviewCardId, quality)
      toast.warning("Mất kết nối, kết quả đã lưu tạm — sẽ đồng bộ lại khi có mạng")
    } finally {
      setIsRating(false)
    }
  }

  const [isUpdatingSchedule, setIsUpdatingSchedule] = React.useState(false)

  const handleConfirmUpdate = async (shouldUpdate: boolean) => {
    if (!shouldUpdate) {
      onFinish()
      return
    }

    setIsUpdatingSchedule(true)
    try {
      const res = await fetch("/api/review/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          set_id: set.id,
          reviews: results.map(r => ({ card_id: r.card_id, quality: r.quality }))
        })
      })

      if (res.ok) {
        toast.success("Đã cập nhật lộ trình mới!")
        onFinish()
      } else {
        throw new Error("Lỗi cập nhật")
      }
    } catch (err) {
      toast.error("Không thể cập nhật lộ trình")
    } finally {
      setIsUpdatingSchedule(false)
    }
  }

  const playAudio = (url?: string) => {
    if (!url) return
    const fullUrl = url.startsWith('http') || url.startsWith('/api') 
      ? url 
      : `/api/audio?filename=${url}`
    const audio = new Audio(fullUrl)
    audio.play().catch(() => toast.error("Không thể phát âm thanh"))
  }

  React.useEffect(() => {
    if (isFinished && results.length > 0) {
      const accuracy = (results.filter(r => r.quality >= 4).length / results.length) * 100
      fetch("/api/analytics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: `Ôn tập bộ thẻ: ${set.name}`,
          mode: "study_review",
          cardCount: results.length,
          levelStats: { accuracy: Math.round(accuracy) },
          isRAG: false
        })
      }).catch(err => console.error("Lỗi log session:", err))

      // Flush pending reviews khi hoàn thành session
      flushPendingReviews()
    }
  }, [isFinished, results, set.name]) // eslint-disable-line react-hooks/exhaustive-deps

  if (isFinished) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-8 animate-in zoom-in-95 duration-500">
        <div className="relative">
          <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full animate-pulse" />
          <div className="relative bg-white p-8 rounded-full shadow-2xl border-4 border-primary/10">
             <Trophy className="w-20 h-20 text-primary animate-bounce" />
          </div>
        </div>
        
        <div className="text-center space-y-2">
          <h2 className="text-4xl font-black tracking-tight">Tuyệt vời!</h2>
          <p className="text-muted-foreground text-lg">Bạn đã hoàn thành bộ thẻ <strong>{set.name}</strong></p>
        </div>

        <div className="grid grid-cols-3 gap-6 w-full max-w-2xl">
           <Card className="bg-green-50 border-green-100 text-center p-6">
              <h4 className="text-xs font-bold text-green-600 uppercase tracking-widest mb-1">Nhớ tốt</h4>
              <p className="text-3xl font-black">{results.filter(r => r.quality >= 4).length}</p>
           </Card>
           <Card className="bg-orange-50 border-orange-100 text-center p-6">
              <h4 className="text-xs font-bold text-orange-600 uppercase tracking-widest mb-1">Cần ôn lại</h4>
              <p className="text-3xl font-black">{results.filter(r => r.quality > 0 && r.quality < 4).length}</p>
           </Card>
           <Card className="bg-red-50 border-red-100 text-center p-6">
              <h4 className="text-xs font-bold text-red-600 uppercase tracking-widest mb-1">Đã quên</h4>
              <p className="text-3xl font-black">{results.filter(r => r.quality === 0).length}</p>
           </Card>
        </div>

        {set.isEarly ? (
          <div className="flex flex-col items-center gap-6 w-full max-w-md">
            <div className="bg-blue-50 border border-blue-100 p-6 rounded-2xl text-center space-y-2">
              <p className="text-sm font-bold text-blue-700 uppercase tracking-widest">Học trước kế hoạch</p>
              <p className="text-xs text-blue-600/80 leading-relaxed">
                Bạn vừa hoàn thành ôn tập sớm. Bạn có muốn cập nhật kết quả này vào lộ trình SM-2 không?
                <br />
                <span className="font-bold text-blue-700 mt-1 block">
                  💡 Khuyến cáo: Nên giữ nguyên kế hoạch để đạt hiệu quả ghi nhớ cao nhất theo khoa học.
                </span>
              </p>
            </div>
            <div className="flex gap-4 w-full">
              <Button 
                variant="outline" 
                onClick={() => handleConfirmUpdate(false)}
                className="flex-1 rounded-full py-7 font-bold border-2"
                disabled={isUpdatingSchedule}
              >
                Giữ nguyên lịch cũ
              </Button>
              <Button 
                onClick={() => handleConfirmUpdate(true)}
                className="flex-1 rounded-full py-7 font-bold shadow-xl shadow-primary/20"
                disabled={isUpdatingSchedule}
              >
                {isUpdatingSchedule ? <Loader2 className="w-5 h-5 animate-spin" /> : "Cập nhật lộ trình"}
              </Button>
            </div>
          </div>
        ) : (
          <Button onClick={onFinish} className="rounded-full px-12 py-7 text-lg font-bold shadow-xl shadow-primary/20">
             Quay lại
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between px-2">
        <Button variant="ghost" size="sm" onClick={onFinish} className="gap-2">
          <ChevronLeft className="w-4 h-4" /> Thoát
        </Button>
        <div className="flex flex-col items-end">
           <span className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em]">Tiến độ ôn tập</span>
           <span className="text-sm font-bold text-primary">{currentIndex + 1} / {cards.length}</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Progress value={progress} className="h-1.5 bg-muted/50 flex-1" />
        {pendingCount > 0 && (
          <Badge className="bg-yellow-100 text-yellow-700 border-yellow-200 text-[10px] font-bold animate-pulse">
            ⏳ {pendingCount} chờ đồng bộ
          </Badge>
        )}
      </div>

      {/* Main Flashcard for Study */}
      <div className="perspective-1000 h-[380px] w-full" onClick={() => setIsFlipped(!isFlipped)}>
        <div className={cn(
          "relative h-full w-full transition-all duration-700 preserve-3d cursor-pointer",
          isFlipped ? "rotate-y-180" : ""
        )}>
          {/* Front */}
          <Card className="absolute inset-0 [backface-visibility:hidden] [transform:translateZ(0)] p-8 flex flex-col items-center justify-center text-center shadow-notion border-border/50 bg-white">
            <div className="absolute top-6 left-6">
              <Badge className="bg-zinc-100 text-zinc-600 border-zinc-200">
                {currentCard.level || "Flashcard"}
              </Badge>
            </div>
            
            <div className="absolute top-6 right-6 flex gap-2">
              {currentCard.note && (
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className={cn(
                    "h-9 w-9 rounded-full transition-all hover:bg-yellow-50",
                    showNote ? "text-yellow-600 bg-yellow-50" : "text-zinc-400"
                  )}
                  onClick={(e) => { e.stopPropagation(); setShowNote(!showNote); }}
                >
                  <StickyNote className="w-4 h-4" />
                </Button>
              )}
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-9 w-9 rounded-full hover:bg-red-50 hover:text-red-500"
                onClick={(e) => { e.stopPropagation(); handleDeleteCard(); }}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-9 w-9 rounded-full hover:bg-zinc-100"
                onClick={(e) => { e.stopPropagation(); setIsEditorOpen(true); }}
              >
                <Pencil className="w-4 h-4" />
              </Button>
            </div>
            
            <div className="space-y-3">
              <h3 className="text-2xl font-bold leading-tight text-zinc-800">
                 {currentCard.question.split('\n')[0]}
              </h3>
              
              {/* Phiên âm và Loại từ - Nằm cạnh nhau, không in nghiêng */}
              <div className="flex items-center justify-center gap-3">
                {(currentCard.phonetic || currentCard.ipa || currentCard.question.includes('\n')) && (
                  <p className="text-base font-medium text-primary/70 font-mono">
                    {currentCard.phonetic || currentCard.ipa || currentCard.question.split('\n')[1]}
                  </p>
                )}
                {(currentCard.part_of_speech || currentCard.type) && (
                  <span className="text-sm font-black text-primary/40 uppercase tracking-widest bg-primary/5 px-3 py-1 rounded-full">
                    {currentCard.part_of_speech || currentCard.type}
                  </span>
                )}
              </div>

              {/* Nút phát âm thanh */}
              {(currentCard.audio_url || currentCard.audio) && (
                <Button 
                  variant="secondary" 
                  size="icon" 
                  className="rounded-full h-12 w-12 shadow-lg hover:scale-110 transition-transform bg-primary/5 text-primary border-primary/10"
                  onClick={(e) => { e.stopPropagation(); playAudio(currentCard.audio_url || currentCard.audio) }}
                >
                  <Volume2 className="w-6 h-6" />
                </Button>
              )}

              {/* Note Preview Front */}
              {showNote && currentCard.note && (
                <div className="mt-4 p-3 bg-yellow-50/80 border border-yellow-100 rounded-xl text-sm text-yellow-800 italic leading-snug animate-in fade-in slide-in-from-top-2 duration-300 max-w-[80%]">
                   <span className="font-bold mr-1">Note:</span>
                   {currentCard.note}
                </div>
              )}
            </div>

            <div className="absolute bottom-10 text-muted-foreground flex items-center gap-2 animate-pulse">
               <Zap className="w-4 h-4 text-yellow-500" />
               <span className="text-[10px] uppercase font-black tracking-widest">Nhấp để xem đáp án</span>
            </div>
          </Card>

          {/* Back */}
          <Card className="absolute inset-0 [backface-visibility:hidden] [transform:rotateY(180deg)_translateZ(0)] p-8 flex flex-col items-center justify-center text-center shadow-notion border-border/50 bg-primary/[0.03]">
            <div className="absolute top-6 right-6 flex gap-2">
              {currentCard.note && (
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className={cn(
                    "h-8 w-8 rounded-full transition-all",
                    showNote ? "text-yellow-600 bg-yellow-50" : "text-zinc-400"
                  )}
                  onClick={(e) => { e.stopPropagation(); setShowNote(!showNote); }}
                >
                  <StickyNote className="w-3.5 h-3.5" />
                </Button>
              )}
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8 rounded-full hover:bg-zinc-100"
                onClick={(e) => { e.stopPropagation(); setIsEditorOpen(true); }}
              >
                <Pencil className="w-3.5 h-3.5" />
              </Button>
            </div>
            <Badge className="mb-6 bg-primary/10 text-primary border-primary/20">ANSWER</Badge>
            <p className="text-lg font-medium leading-relaxed text-zinc-700">
               {currentCard.answer}
            </p>

            {/* Note Preview Back */}
            {showNote && currentCard.note && (
              <div className="mt-6 p-4 bg-yellow-50/50 border-l-4 border-yellow-400 rounded-r-xl text-sm text-yellow-900 text-left leading-relaxed animate-in fade-in zoom-in-95 duration-300 max-w-[90%]">
                 <div className="flex items-center gap-2 mb-1">
                   <StickyNote className="w-3.5 h-3.5 text-yellow-600" />
                   <span className="font-black uppercase tracking-widest text-[10px]">Ghi chú bổ sung</span>
                 </div>
                 {currentCard.note}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Rating Buttons - Only show when flipped */}
      <div className={cn(
        "grid grid-cols-4 gap-4 transition-all duration-500",
        isFlipped ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10 pointer-events-none"
      )}>
        <Button 
          variant="outline" 
          className="h-20 flex-col gap-2 rounded-2xl hover:bg-red-50 hover:text-red-600 hover:border-red-200 disabled:opacity-50 disabled:pointer-events-none"
          onClick={() => handleRate(1)}
          disabled={isRating}
        >
          <span className="text-xl">😫</span>
          <span className="text-[10px] font-bold uppercase">Lặp lại</span>
        </Button>
        <Button 
          variant="outline" 
          className="h-20 flex-col gap-2 rounded-2xl hover:bg-orange-50 hover:text-orange-600 hover:border-orange-200 disabled:opacity-50 disabled:pointer-events-none"
          onClick={() => handleRate(2)}
          disabled={isRating}
        >
          <span className="text-xl">🤨</span>
          <span className="text-[10px] font-bold uppercase">Khó</span>
        </Button>
        <Button 
          variant="outline" 
          className="h-20 flex-col gap-2 rounded-2xl hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 disabled:opacity-50 disabled:pointer-events-none"
          onClick={() => handleRate(3)}
          disabled={isRating}
        >
          <span className="text-xl">🙂</span>
          <span className="text-[10px] font-bold uppercase">Tốt</span>
        </Button>
        <Button 
          variant="outline" 
          className="h-20 flex-col gap-2 rounded-2xl hover:bg-green-50 hover:text-green-600 hover:border-green-200 disabled:opacity-50 disabled:pointer-events-none"
          onClick={() => handleRate(4)}
          disabled={isRating}
        >
          <span className="text-xl">🤩</span>
          <span className="text-[10px] font-bold uppercase">Dễ</span>
        </Button>
      </div>

      <FlashcardEditor 
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        card={currentCard}
        onSave={handleUpdateCard}
      />

      <div className="flex justify-center text-zinc-400 gap-6 text-xs font-medium">
         <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" /> Thuật toán FSRS Active
         </div>
         <div className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" /> AI Learning Engine
         </div>
      </div>
    </div>
  )
}
