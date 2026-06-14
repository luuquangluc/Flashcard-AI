"use client"

import * as React from "react"
import { Volume2, Pencil, Undo2, Trash2, StickyNote } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { FlashcardEditor } from "./flashcard-editor"

interface FlashcardProps {
  card: {
    id?: string | number
    question: string
    answer: string
    level?: string
    audio_url?: string
    audio?: string
    pdf_url?: string
    original_pdf_url?: string
    bboxes?: any[]
    phonetic?: string
    ipa?: string
    part_of_speech?: string
    type?: string
    note?: string
    context?: string
  }
  onUpdate?: (newQuestion: string, newAnswer: string, newNote: string) => void
  onDelete?: () => void
}

export function Flashcard({ 
  card,
  onUpdate,
  onDelete
}: FlashcardProps) {
  const [isFlipped, setIsFlipped] = React.useState(false)
  const [isEditorOpen, setIsEditorOpen] = React.useState(false)
  const [showNote, setShowNote] = React.useState(false)
  
  const phonetic = card.phonetic || card.ipa
  const pos = card.part_of_speech || card.type

  // Audio handling
  let audioUrl = card.audio_url || card.audio
  if (audioUrl && !audioUrl.startsWith('http') && !audioUrl.startsWith('/api')) {
    audioUrl = `/api/audio?filename=${audioUrl}`
  }

  const getLevelColor = (lvl?: string) => {
    switch (lvl) {
      case "Nhận biết": return "bg-green-100 text-green-700 border-green-200"
      case "Thông hiểu": return "bg-orange-100 text-orange-700 border-orange-200"
      case "Vận dụng": return "bg-red-100 text-red-700 border-red-200"
      case "Từ vựng": return "bg-blue-100 text-blue-700 border-blue-200"
      default: return "bg-gray-100 text-gray-700 border-gray-200"
    }
  }

  const handleSave = (newQuestion: string, newAnswer: string, newNote: string) => {
    setIsEditorOpen(false)
    if (onUpdate) onUpdate(newQuestion, newAnswer, newNote)
  }

  const toggleFlip = () => {
    if (!isEditorOpen) setIsFlipped(!isFlipped)
  }

  return (
    <>
      <div 
        className="group perspective-1000 h-[320px] w-full cursor-pointer"
        onClick={toggleFlip}
      >
        <div className={cn(
          "relative h-full w-full transition-all duration-500 preserve-3d",
          isFlipped ? "rotate-y-180" : ""
        )}>
          {/* Front */}
          <Card className="absolute inset-0 [backface-visibility:hidden] [transform:translateZ(0)] p-6 flex flex-col shadow-notion border-border/50 bg-white hover:border-primary/30 transition-colors">
            <div className="flex justify-between items-start mb-4">
              <Badge variant="outline" className={cn("font-semibold", getLevelColor(card.level))}>
                {card.level || "AI Generated"}
              </Badge>
              <div className="flex gap-1">
                {card.note && (
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className={cn(
                      "h-8 w-8 rounded-full transition-all hover:bg-yellow-50",
                      showNote ? "text-yellow-600 bg-yellow-50" : "text-zinc-400"
                    )}
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowNote(!showNote)
                    }}
                  >
                    <StickyNote className="w-4 h-4" />
                  </Button>
                )}
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-50 hover:text-red-500"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (onDelete) onDelete()
                  }}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-zinc-100"
                  onClick={(e) => {
                    e.stopPropagation()
                    setIsEditorOpen(true)
                  }}
                >
                  <Pencil className="w-3.5 h-3.5" />
                </Button>
                {audioUrl && (
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="h-8 w-8 rounded-full"
                    onClick={(e) => {
                      e.stopPropagation()
                      const audio = new Audio(audioUrl)
                      audio.play()
                    }}
                  >
                    <Volume2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
            
            <div className="flex-1 flex flex-col items-center justify-center text-center px-2 space-y-1">
               <h3 className="text-xl font-bold leading-relaxed tracking-tight text-zinc-800">
                 {card.question.split('\n')[0]}
               </h3>
               <div className="flex items-center gap-2">
                 {(phonetic || card.question.includes('\n')) && (
                   <p className="text-sm font-medium text-primary/60 font-mono">
                     {phonetic || card.question.split('\n')[1]}
                   </p>
                 )}
                 {pos && (
                   <span className="text-[10px] font-bold text-primary/40 uppercase tracking-tighter">
                     ({pos})
                   </span>
                 )}
               </div>

               {/* Note Preview Front */}
               {showNote && card.note && (
                 <div className="mt-4 p-3 bg-yellow-50/80 border border-yellow-100 rounded-xl text-[11px] text-yellow-800 italic leading-snug animate-in fade-in slide-in-from-top-2 duration-300">
                    <span className="font-bold mr-1 NOT-ITALIC">Note:</span>
                    {card.note}
                 </div>
               )}
            </div>
            
            <div className="mt-auto text-center text-[10px] text-muted-foreground uppercase tracking-widest font-bold opacity-0 group-hover:opacity-100 transition-opacity">
               Nhấp để xem đáp án ⤵
            </div>
          </Card>

          {/* Back */}
          <Card className="absolute inset-0 [backface-visibility:hidden] [transform:rotateY(180deg)_translateZ(0)] p-6 flex flex-col shadow-notion border-border/50 bg-secondary/30">
            <div className="flex justify-between items-center mb-4">
              <Badge variant="outline" className={cn("font-semibold", getLevelColor(card.level))}>
                {card.level || "AI Generated"}
              </Badge>
              <div className="flex gap-1">
                {card.note && (
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className={cn(
                      "h-8 w-8 rounded-full transition-all",
                      showNote ? "text-yellow-600 bg-yellow-50" : "text-zinc-400"
                    )}
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowNote(!showNote)
                    }}
                  >
                    <StickyNote className="w-4 h-4" />
                  </Button>
                )}
                <Button 
                   variant="ghost" 
                   size="icon" 
                   className="h-8 w-8 rounded-full"
                   onClick={(e) => {
                     e.stopPropagation()
                     setIsFlipped(false)
                   }}
                 >
                   <Undo2 className="w-3.5 h-3.5" />
                 </Button>
              </div>
            </div>
            
            <div className="flex-1 flex flex-col items-center justify-center text-center px-2">
               <p className="text-lg font-medium leading-relaxed text-zinc-700">
                 <span className="text-green-600 mr-2 font-bold italic">A:</span>
                 {card.answer}
               </p>

               {/* Note Preview Back */}
               {showNote && card.note && (
                 <div className="mt-6 p-4 bg-yellow-50/50 border-l-4 border-yellow-400 rounded-r-xl text-xs text-yellow-900 text-left leading-relaxed animate-in fade-in zoom-in-95 duration-300">
                    <div className="flex items-center gap-2 mb-1">
                      <StickyNote className="w-3 h-3 text-yellow-600" />
                      <span className="font-black uppercase tracking-widest text-[9px]">Ghi chú bổ sung</span>
                    </div>
                    {card.note}
                 </div>
               )}
            </div>
            
            <div className="mt-auto text-center text-[10px] text-muted-foreground uppercase tracking-widest font-bold opacity-40">
               Nhấp để lật lại ⤴
            </div>
          </Card>
        </div>
      </div>

      <FlashcardEditor 
        isOpen={isEditorOpen}
        onClose={() => setIsEditorOpen(false)}
        card={card}
        onSave={handleSave}
      />
    </>
  )
}
