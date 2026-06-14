"use client"

import * as React from "react"
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle,
  DialogDescription,
  DialogFooter
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { FileText, Save, X, ExternalLink, Loader2, Maximize2, Pencil, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

interface FlashcardEditorProps {
  isOpen: boolean
  onClose: () => void
  card: {
    id?: string | number
    question: string
    answer: string
    level?: string
    pdf_url?: string
    original_pdf_url?: string
    bboxes?: any[]
    note?: string
    context?: string
  }
  onSave: (question: string, answer: string, note: string) => void
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export function FlashcardEditor({ isOpen, onClose, card, onSave }: FlashcardEditorProps) {
  const hasPdf = React.useMemo(() => {
    return (card.bboxes && card.bboxes.length > 0) || !!card.pdf_url
  }, [card.bboxes, card.pdf_url])

  const isTranscript = React.useMemo(() => {
    const url = card.original_pdf_url || ""
    return url.toLowerCase().split('?')[0].endsWith('.txt')
  }, [card.original_pdf_url])

  const [question, setQuestion] = React.useState(card.question)
  const [answer, setAnswer] = React.useState(card.answer)
  const [note, setNote] = React.useState(card.note || "")
  const [pdfLoading, setPdfLoading] = React.useState(true)
  const [docContent, setDocContent] = React.useState<string | null>(null)
  
  // AI Chat state
  const [messages, setMessages] = React.useState<Message[]>([])
  const [inputValue, setInputValue] = React.useState("")
  const [isChatLoading, setIsChatLoading] = React.useState(false)
  const scrollRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    setQuestion(card.question)
    setAnswer(card.answer)
    setNote(card.note || "")
    if (!hasPdf) {
      setPdfLoading(false)
      fetch('/api/document/content')
        .then(res => res.json())
        .then(data => {
           if (data.success && data.content) {
             setDocContent(data.content)
           } else {
             setDocContent(null)
           }
        })
        .catch(err => {
           console.error(err)
           setDocContent(null)
        })
    } else {
      setPdfLoading(true)
    }

    setMessages([{
      role: 'assistant',
      content: `Chào bạn! Tôi là AI hỗ trợ học tập. ${hasPdf ? "Tôi đã đọc phần nội dung tài liệu liên quan đến thẻ này." : "Thẻ này được tạo từ kiến thức chung của tôi."} Bạn có thắc mắc gì về kiến thức này không?`
    }])
  }, [card, hasPdf])

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isChatLoading) return

    const userMsg = inputValue.trim()
    setInputValue("")
    const newMessages: Message[] = [...messages, { role: 'user', content: userMsg }]
    setMessages(newMessages)
    setIsChatLoading(true)

    try {
      const res = await fetch("/api/flashcard/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: card.context || "", // Gửi ngữ cảnh gốc từ PDF
          question: question,
          answer: answer,
          message: userMsg,
          history: messages.slice(1) // Bỏ tin nhắn chào đầu tiên
        })
      })

      const data = await res.json()

      if (!res.ok) {
        // Guardrail blocked hoặc lỗi server
        const errorMsg = data.error || "Lỗi kết nối AI"
        if (data.guardrail_blocked) {
          // Hiển thị cảnh báo guardrail trực tiếp trong chat
          setMessages([...newMessages, { role: 'assistant', content: errorMsg }])
        } else {
          toast.error(errorMsg)
          setMessages([...newMessages, { role: 'assistant', content: errorMsg }])
        }
        return
      }

      setMessages([...newMessages, { role: 'assistant', content: data.response }])
    } catch (err) {
      toast.error("Không thể kết nối với AI Assistant")
      setMessages([...newMessages, { role: 'assistant', content: "Xin lỗi, tôi gặp trục trặc kỹ thuật. Vui lòng thử lại sau." }])
    } finally {
      setIsChatLoading(false)
    }
  }
  const [localPdfUrl, setLocalPdfUrl] = React.useState<string | null>(null)

  React.useEffect(() => {
    let url = ""
    async function loadLocalPdf() {
      try {
        const { getFile } = await import("@/lib/idb")
        const filename = `card_highlight_${card.id}`
        const file = await getFile(filename)
        if (file && file instanceof Blob) {
          url = URL.createObjectURL(file)
          setLocalPdfUrl(url)
        } else {
          setLocalPdfUrl(null)
        }
      } catch (e) {
        console.error("Lỗi đọc file từ IndexedDB:", e)
        setLocalPdfUrl(null)
      }
    }
    loadLocalPdf()
    return () => {
      if (url) {
        URL.revokeObjectURL(url)
      }
    }
  }, [card.id])

  const pdfUrl = React.useMemo(() => {
    const filename = `card_highlight_${card.id}.pdf`
    let fragment = ""

    if (card.bboxes && card.bboxes.length > 0) {
      const pageCounts: Record<number, number> = {}
      card.bboxes.forEach(b => {
        const p = b.p || 1
        pageCounts[p] = (pageCounts[p] || 0) + 1
      })
      
      let maxCount = 0
      let targetPage = 1
      for (const p in pageCounts) {
        const pageNum = parseInt(p)
        if (pageCounts[pageNum] > maxCount) {
          maxCount = pageCounts[pageNum]
          targetPage = pageNum
        }
      }

      const pageBboxes = card.bboxes.filter(b => b.p === targetPage)
      let y0_min = Infinity
      let y1_max = -Infinity
      pageBboxes.forEach(b => {
        const [x0, y0, x1, y1] = b.b
        y0_min = Math.min(y0_min, y0)
        y1_max = Math.max(y1_max, y1)
      })

      const PAGE_HEIGHT = 842
      const y_center = (y0_min + y1_max) / 2
      const pdfTop = PAGE_HEIGHT - y_center - 250
      const safePdfTop = Math.max(0, pdfTop)
      
      fragment = `#page=${targetPage}&view=FitH,${Math.round(safePdfTop)}&zoom=150`
    }

    const baseUrl = localPdfUrl ? localPdfUrl : (card.pdf_url ? card.pdf_url : `/api/pdf?filename=${filename}`)
    return `${baseUrl}${fragment}`
  }, [card.id, card.pdf_url, card.bboxes, localPdfUrl])

  const [originalFileUrl, setOriginalFileUrl] = React.useState<string | null>(null)

  React.useEffect(() => {
    let url = ""
    async function loadOriginalPdf() {
      try {
        if (!card.original_pdf_url) return
        const { getFile } = await import("@/lib/idb")
        const file = await getFile(card.original_pdf_url)
        if (file && file instanceof Blob) {
          url = URL.createObjectURL(file)
          setOriginalFileUrl(url)
        } else {
          setOriginalFileUrl(null)
        }
      } catch (e) {
        console.error("Lỗi đọc file gốc từ IndexedDB:", e)
        setOriginalFileUrl(null)
      }
    }
    if (card.original_pdf_url && card.original_pdf_url.startsWith("original_pdf_")) {
      loadOriginalPdf()
    }
    return () => {
      if (url) {
        URL.revokeObjectURL(url)
      }
    }
  }, [card.original_pdf_url])

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[96vw] w-[96vw] h-[94vh] flex flex-col p-0 overflow-hidden border-none shadow-2xl rounded-2xl">
        <DialogHeader className="p-4 px-10 border-b bg-white shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-5">
              <div className="bg-primary/10 p-3 rounded-2xl">
                <FileText className="w-7 h-7 text-primary" />
              </div>
              <div>
                <DialogTitle className="text-2xl font-black tracking-tight text-zinc-900">Trình biên tập Flashcard chuyên sâu</DialogTitle>
                <DialogDescription className="sr-only">
                  Chỉnh sửa nội dung câu hỏi và câu trả lời của thẻ flashcard đồng thời xem nguồn tài liệu PDF.
                </DialogDescription>
                <div className="flex items-center gap-4 mt-1">
                   <Badge variant="secondary" className="text-[11px] h-6 px-3 font-black uppercase tracking-widest bg-zinc-900 text-white">
                     {card.level || "LEVEL"}
                   </Badge>
                   <span className="text-sm text-zinc-400 font-bold tracking-widest uppercase">
                      Document ID: {card.id}
                   </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4">
               <Button variant="outline" size="lg" className="h-11 gap-3 rounded-full border-zinc-200 px-6 hover:bg-zinc-50 transition-all font-bold" asChild>
                  <a href={isTranscript && card.original_pdf_url ? `/api/transcript?url=${encodeURIComponent(card.original_pdf_url)}` : (originalFileUrl || card.original_pdf_url || pdfUrl.split('#')[0])} target="_blank" rel="noreferrer">
                    <Maximize2 className="w-5 h-5" />
                    {isTranscript ? "Xem file transcript" : "Bật chế độ đọc tập trung"}
                  </a>
               </Button>
               <Button variant="ghost" size="icon" className="h-12 w-12 rounded-full bg-zinc-100 hover:bg-zinc-200" onClick={onClose}>
                  <X className="w-6 h-6 text-zinc-600" />
               </Button>
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 flex overflow-hidden">
          {/* Cột trái: Tabs (30%) - Mở rộng một chút để chứa Chat */}
          <div className="w-[30%] min-w-[400px] flex flex-col bg-white border-r border-zinc-100 shadow-[15px_0_40px_-20px_rgba(0,0,0,0.08)] z-10 overflow-hidden">
            <Tabs defaultValue="edit" className="flex-1 flex flex-col min-h-0">
              <div className="px-6 pt-4">
                <TabsList className="w-full bg-zinc-100/50 p-1 rounded-2xl">
                  <TabsTrigger value="edit" className="flex-1 gap-2 rounded-xl py-2 font-bold data-[state=active]:bg-white data-[state=active]:shadow-sm">
                    <Pencil className="w-4 h-4" /> Biên tập
                  </TabsTrigger>
                  <TabsTrigger value="ai" className="flex-1 gap-2 rounded-xl py-2 font-bold data-[state=active]:bg-white data-[state=active]:shadow-sm">
                    <Sparkles className="w-4 h-4 text-primary" /> AI Assistant
                  </TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="edit" className="flex-1 overflow-y-auto p-10 mt-0 space-y-10 min-h-0">
                <div className="space-y-4">
                  <Label className="text-[12px] font-black uppercase tracking-[0.3em] text-zinc-400 pl-1">Câu hỏi (Front)</Label>
                  <Textarea 
                    value={question} 
                    onChange={(e) => setQuestion(e.target.value)}
                    className="min-h-[220px] text-xl font-bold p-8 bg-zinc-50 border-none focus-visible:ring-2 focus-visible:ring-primary/20 rounded-3xl resize-none leading-relaxed shadow-inner"
                    placeholder="Nội dung câu hỏi..."
                  />
                </div>

                <div className="space-y-4">
                  <Label className="text-[12px] font-black uppercase tracking-[0.3em] text-zinc-400 pl-1">Câu trả lời (Back)</Label>
                  <Textarea 
                    value={answer} 
                    onChange={(e) => setAnswer(e.target.value)}
                    className="min-h-[300px] text-lg font-medium p-8 bg-zinc-50 border-none focus-visible:ring-2 focus-visible:ring-primary/20 rounded-3xl resize-none leading-relaxed shadow-inner"
                    placeholder="Nội dung câu trả lời..."
                  />
                </div>

                <div className="space-y-4">
                  <Label className="text-[12px] font-black uppercase tracking-[0.3em] text-zinc-400 pl-1">Ghi chú (Note)</Label>
                  <Textarea 
                    value={note} 
                    onChange={(e) => setNote(e.target.value)}
                    className="min-h-[150px] text-sm font-medium p-6 bg-yellow-50/50 border-dashed border-yellow-200 focus-visible:ring-2 focus-visible:ring-yellow-200/50 rounded-2xl resize-none leading-relaxed"
                    placeholder="Thêm thông tin bổ sung cho thẻ này..."
                  />
                </div>
              </TabsContent>

              <TabsContent value="ai" className="flex-1 data-[state=active]:flex flex-col mt-0 overflow-hidden min-h-0">
                <div 
                  ref={scrollRef}
                  className="flex-1 overflow-y-auto p-6 space-y-6 bg-zinc-50/30 min-h-0"
                >
                  {messages.map((msg, i) => (
                    <div key={i} className={cn(
                      "flex flex-col max-w-[85%]",
                      msg.role === 'user' ? "ml-auto items-end" : "mr-auto items-start"
                    )}>
                      <div className={cn(
                        "p-4 rounded-2xl text-sm leading-relaxed",
                        msg.role === 'user' 
                          ? "bg-primary text-white rounded-tr-none shadow-lg shadow-primary/20" 
                          : "bg-white text-zinc-700 rounded-tl-none border border-zinc-100 shadow-sm"
                      )}>
                        {msg.content}
                      </div>
                      <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-widest mt-1 px-1">
                        {msg.role === 'user' ? 'Bạn' : 'AI Assistant'}
                      </span>
                    </div>
                  ))}
                  {isChatLoading && (
                    <div className="flex gap-2 items-center text-zinc-400 px-2">
                       <Loader2 className="w-4 h-4 animate-spin" />
                       <span className="text-xs font-bold uppercase tracking-widest">Đang suy nghĩ...</span>
                    </div>
                  )}
                </div>
                
                <div className="p-4 bg-white border-t border-zinc-100">
                  <div className="relative">
                    <Textarea 
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          handleSendMessage()
                        }
                      }}
                      placeholder="Hỏi AI về nội dung này..."
                      className="pr-14 min-h-[100px] max-h-[200px] bg-zinc-50 border-none rounded-2xl focus-visible:ring-primary/20 resize-none py-4 px-5 font-medium"
                    />
                    <Button 
                      size="icon"
                      onClick={handleSendMessage}
                      disabled={!inputValue.trim() || isChatLoading}
                      className="absolute right-3 bottom-3 h-10 w-10 rounded-xl shadow-lg shadow-primary/20"
                    >
                      <Sparkles className="w-5 h-5" />
                    </Button>
                  </div>
                  <p className="text-[10px] text-center text-zinc-400 mt-3 font-bold uppercase tracking-widest">
                    AI sử dụng ngữ cảnh từ đoạn PDF đang hiển thị
                  </p>
                </div>
              </TabsContent>
            </Tabs>
          </div>

          {/* Cột phải: PDF Viewer hoặc AI Knowledge Placeholder */}
          <div className="flex-1 flex flex-col relative bg-[#323639]">
            {hasPdf ? (
              <>
                {pdfLoading && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-900/90 z-20 backdrop-blur-md">
                    <Loader2 className="w-16 h-16 animate-spin text-primary mb-6" />
                    <p className="text-lg font-black text-zinc-400 uppercase tracking-[0.5em]">Đang đồng bộ kiến thức...</p>
                  </div>
                )}
                <iframe 
                  src={pdfUrl}
                  className="w-full h-full border-none"
                  onLoad={() => setPdfLoading(false)}
                />
              </>
            ) : isTranscript && card.context ? (
              <div className="w-full h-full flex flex-col bg-white overflow-y-auto relative z-10">
                <div className="p-8 border-b bg-white sticky top-0 z-20 shadow-sm flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="bg-primary/10 p-3 rounded-2xl">
                      <FileText className="w-7 h-7 text-primary" />
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-zinc-900 tracking-tight">Ngữ cảnh của thẻ (Chunk)</h3>
                      <p className="text-sm text-zinc-500 font-medium">Được trích xuất từ video làm cơ sở tạo thẻ này</p>
                    </div>
                  </div>
                </div>
                <div className="p-8">
                  <div className="prose max-w-none text-zinc-700 leading-loose font-medium text-[15px] whitespace-pre-wrap bg-zinc-50/80 p-8 rounded-3xl border border-zinc-100 shadow-inner min-h-[500px]">
                    {card.context}
                  </div>
                </div>
              </div>
            ) : docContent ? (
              <div className="w-full h-full flex flex-col bg-white overflow-y-auto relative z-10">
                <div className="p-8 border-b bg-white sticky top-0 z-20 shadow-sm flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="bg-primary/10 p-3 rounded-2xl">
                      <FileText className="w-7 h-7 text-primary" />
                    </div>
                    <div>
                      <h3 className="text-xl font-black text-zinc-900 tracking-tight">Nội dung văn bản gốc</h3>
                      <p className="text-sm text-zinc-500 font-medium">Được dùng làm ngữ cảnh cho hệ thống RAG sinh thẻ</p>
                    </div>
                  </div>
                </div>
                <div className="p-8">
                  <div className="prose max-w-none text-zinc-700 leading-loose font-medium text-[15px] whitespace-pre-wrap bg-zinc-50/80 p-8 rounded-3xl border border-zinc-100 shadow-inner min-h-[500px]">
                    {docContent}
                  </div>
                </div>
              </div>
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center bg-zinc-950 p-20 text-center">
                <div className="relative mb-10">
                   <div className="absolute -inset-10 bg-primary/20 blur-[100px] rounded-full" />
                   <div className="relative bg-zinc-900 p-8 rounded-[40px] border border-white/10 shadow-2xl">
                      <Sparkles className="w-20 h-20 text-primary animate-pulse" />
                   </div>
                </div>
                <h3 className="text-3xl font-black text-white mb-4 tracking-tight">Kiến thức tổng hợp từ AI</h3>
                <p className="text-zinc-400 max-w-md leading-relaxed text-lg font-medium">
                  Thẻ này được tạo ra từ kho tri thức khổng lồ của AI mà không dựa trên tài liệu PDF cụ thể. 
                  Bạn có thể sử dụng <b>AI Assistant</b> bên trái để mở rộng thêm thông tin!
                </p>
                <div className="mt-12 flex gap-4">
                   <Badge variant="outline" className="text-zinc-500 border-zinc-800 px-6 py-2 rounded-full font-bold uppercase tracking-widest text-[10px]">
                     General Knowledge Mode
                   </Badge>
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="p-6 px-10 border-t bg-white shrink-0 shadow-[0_-10px_30px_-15px_rgba(0,0,0,0.05)]">
          <div className="flex w-full items-center justify-between">
            <div className="flex items-center gap-3">
               <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
               <p className="text-sm font-bold text-zinc-500 uppercase tracking-widest">
                 Live PDF Sync Enabled
               </p>
            </div>
            <div className="flex gap-5">
              <Button variant="ghost" onClick={onClose} className="rounded-full px-10 h-14 font-bold text-zinc-400 hover:text-zinc-900 transition-colors">
                Hủy thay đổi
              </Button>
              <Button onClick={() => onSave(question, answer, note)} className="gap-4 px-16 h-14 rounded-full font-black text-xl shadow-2xl shadow-primary/30 transition-all hover:scale-[1.05] active:scale-95 bg-primary hover:bg-primary/90 text-white">
                <Save className="w-7 h-7" />
                LƯU THẺ NÀY
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
