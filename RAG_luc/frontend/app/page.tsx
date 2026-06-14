"use client"

import * as React from "react"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"
import { GeneratorForm } from "@/components/generator-form"
import { Flashcard } from "@/components/flashcard"
import { LibraryView } from "@/components/library-view"
import { StudyView } from "@/components/study-view"
import { GameView } from "@/components/game-view"
import { MemoryGameView } from "@/components/memory-game-view"
import { ScheduleView } from "@/components/schedule-view"
import { AnalyticsView } from "@/components/analytics-view"
import { AdminAnalyticsView } from "@/components/admin-analytics-view"
import { LobbyView } from "@/components/lobby-view"
import { NotificationBell } from "@/components/notification-bell"
import { Loader2, Sparkles, Terminal, Save, LayoutGrid, Bell, CheckCircle2, FileText, Gamepad2, Brain, Puzzle, User, ChevronDown, Plus, LogOut, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"
import { AuthView } from "@/components/auth-view"

const viewTitles: Record<string, string> = {
  generator: "Tạo Thẻ Flashcard",
  library: "Thư Viện",
  analytics: "Thống Kê",
  schedule: "Lịch Ôn Tập",
  study: "Học Tập",
  game: "Trò Chơi",
}

export default function DashboardPage() {
  const [currentView, setCurrentView] = React.useState("generator")
  const [flashcards, setFlashcards] = React.useState<any[]>([])
  const [isGenerating, setIsGenerating] = React.useState(false)
  const [statusLogs, setStatusLogs] = React.useState<string[]>([])
  const [activeSet, setActiveSet] = React.useState<any>(null)
  const [editingSetId, setEditingSetId] = React.useState<string | null>(null)
  const [gameType, setGameType] = React.useState<'matching' | 'memory' | null>(null)
  const [previousView, setPreviousView] = React.useState<string>("library")
  const [isSaving, setIsSaving] = React.useState(false)
  const [isExporting, setIsExporting] = React.useState(false)
  const [originalFlashcards, setOriginalFlashcards] = React.useState<any[]>([])
  const originalFlashcardsRef = React.useRef<any[]>([]) // Dùng Ref để "khóa" dữ liệu gốc
  const [preloadedDocument, setPreloadedDocument] = React.useState<string | null>(null)
  const [uploadedFile, setUploadedFile] = React.useState<string | null>(null)
  const [fileUrl, setFileUrl] = React.useState<string | null>(null)
  const [fileSize, setFileSize] = React.useState<number>(0)
  const [isSavingDoc, setIsSavingDoc] = React.useState(false)
  const [isDocSaved, setIsDocSaved] = React.useState(false)
  const { user, isLoading, logout } = useAuth()
  
  // Tự động quay về tab "generator" sau khi đăng nhập thành công
  React.useEffect(() => {
    if (user) {
      setCurrentView("generator")
    }
  }, [user])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center">
            <Brain className="w-7 h-7 text-white animate-pulse" />
          </div>
          <p className="text-sm font-medium text-muted-foreground">
            Đang xác thực phiên làm việc...
          </p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <AuthView />
  }

  const handleGenerate = async (payload: any) => {
    setIsGenerating(true)
    setFlashcards([])
    setStatusLogs(["Đang bắt đầu pipeline AI..."])
    setEditingSetId(null) // Tạo thẻ mới → không phải update set cũ
    
    // Ưu tiên tên file từ payload hoặc các giá trị mặc định theo chế độ
    const docName = payload.fileName || (payload.mode === "topic" ? `Chủ đề: ${payload.query}` : "Vocabulary")
    setUploadedFile(docName)
    setFileUrl(payload.fileUrl || null)
    setFileSize(payload.fileSize || 0)
    setIsDocSaved(payload.isSaved || false) // Kế thừa trạng thái đã lưu từ Form hoặc reset nếu mới

    // Dọn dẹp IndexedDB trước khi tạo thẻ mới
    try {
      const { openDB } = await import("@/lib/idb")
      const db = await openDB()
      const tx = db.transaction("files", "readwrite")
      const store = tx.objectStore("files")
      const req = store.getAllKeys()
      req.onsuccess = () => {
        const currentFileKey = `original_pdf_${docName}`
        req.result.forEach(key => {
          if (typeof key === "string") {
            // 1. Xóa file highlight của phiên trước
            if (key.startsWith("card_highlight_")) {
              store.delete(key)
            }
            // 2. Xóa file gốc của các lần trước (giữ lại file của lần này)
            if (key.startsWith("original_pdf_") && key !== currentFileKey) {
              store.delete(key)
            }
          }
        })
        console.log("🧹 Đã dọn dẹp các file cũ không liên quan trong IndexedDB.")
      }
    } catch (e) {
      console.error("Lỗi dọn dẹp IndexedDB:", e)
    }

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: 'include',
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.error || "Không thể sinh thẻ")
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      if (!reader) return

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (line.trim().startsWith("data: ")) {
            try {
              const rawData = line.replace("data: ", "").trim()
              if (!rawData) continue

              const data = JSON.parse(rawData)

              if (data.type === "status") {
                // Chỉ hiện "Đang bắt đầu pipeline AI..." — không cập nhật thêm log chi tiết
                // setStatusLogs(prev => [...prev.slice(-4), data.content])
              } else if (data.type === "result") {
                const freshCards = data.flashcards || []
                
                // Lưu các file highlight vào IndexedDB nếu có
                try {
                  const { saveFile } = await import("@/lib/idb")
                  for (const c of freshCards) {
                    if (c.highlight_pdf_base64) {
                      const byteCharacters = atob(c.highlight_pdf_base64)
                      const byteNumbers = new Array(byteCharacters.length)
                      for (let i = 0; i < byteCharacters.length; i++) {
                        byteNumbers[i] = byteCharacters.charCodeAt(i)
                      }
                      const byteArray = new Uint8Array(byteNumbers)
                      const blob = new Blob([byteArray], { type: 'application/pdf' })
                      await saveFile(`card_highlight_${c.id}`, blob)
                    }
                  }
                } catch (e_idb) {
                  console.error("Lỗi lưu file vào IndexedDB:", e_idb)
                }

                const cardsWithOrigUrl = freshCards.map((c: any) => ({
                  ...c,
                  original_pdf_url: c.original_pdf_url || payload.fileUrl || fileUrl || `original_pdf_${docName}`
                }))
                setFlashcards(cardsWithOrigUrl)
                // Copy sâu tuyệt đối và lưu vào cả State lẫn Ref
                const backup = JSON.parse(JSON.stringify(cardsWithOrigUrl))
                setOriginalFlashcards(backup)
                originalFlashcardsRef.current = JSON.parse(JSON.stringify(cardsWithOrigUrl))
                
                toast.success(`Đã sinh xong ${freshCards.length} thẻ!`)
                setIsGenerating(false)
              } else if (data.type === "error") {
                toast.error(data.content || "Lỗi từ server")
                setIsGenerating(false)
              }
            } catch (e) {
              console.error("Lỗi parse SSE:", e)
            }
          }
        }
      }
    } catch (err: any) {
      toast.error(err.message)
      setIsGenerating(false)
    }
  }

  const handleSaveToLibrary = async () => {
    if (flashcards.length === 0) return

    // Nếu đang sửa bộ thẻ từ library → không hỏi tên, dùng tên cũ
    const isUpdating = !!editingSetId
    let setName: string | null
    if (isUpdating) {
      setName = uploadedFile || `Bộ thẻ ${new Date().toLocaleDateString("vi-VN")}`
    } else {
      setName = prompt("Nhập tên cho bộ thẻ này:", `Bộ thẻ ${new Date().toLocaleDateString("vi-VN")}`)
      if (!setName) return
    }

    setIsSaving(true)
    try {
      // --- DATA FLYWHEEL: So sánh và gửi Feedback ---
      const feedbackEvents: any[] = []
      
      try {
        // 1. Tìm các thẻ bị xóa
        originalFlashcardsRef.current.forEach(orig => {
          const stillExists = flashcards.find(f => f.id === orig.id)
          if (!stillExists) {
            feedbackEvents.push({
              feedback_type: "DELETE",
              original_card: { question: orig.question, answer: orig.answer },
              mode: orig.level === "Từ vựng" ? "vocabulary" : "content",
              document_name: uploadedFile
            })
          }
        })

        // 2. Tìm các thẻ bị sửa
        flashcards.forEach((curr) => {
          const orig = originalFlashcardsRef.current.find(f => f.id === curr.id)
          if (orig) {
            const qChanged = orig.question.trim() !== curr.question.trim()
            const aChanged = orig.answer.trim() !== curr.answer.trim()
            
            if (qChanged || aChanged) {
              feedbackEvents.push({
                feedback_type: "EDIT",
                original_card: { question: orig.question, answer: orig.answer },
                corrected_card: { question: curr.question, answer: curr.answer },
                mode: curr.level === "Từ vựng" ? "vocabulary" : "content",
                document_name: uploadedFile
              })
            }
          }
        })

        // Gửi tất cả feedback (Không chặn tiến trình lưu nếu gặp lỗi)
        if (feedbackEvents.length > 0) {
          fetch("/api/feedback/log", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ events: feedbackEvents }),
            credentials: 'include',
          }).catch(err => console.error("Feedback error:", err))
        }
      } catch (err) {
        console.error("Flywheel error:", err)
      }

      // --- TIẾN HÀNH LƯU / CẬP NHẬT BỘ THẺ ---
      let res: Response
      if (isUpdating) {
        // Ghi đè bộ thẻ cũ (PUT)
        res = await fetch(`/api/library/${editingSetId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: setName,
            cards: flashcards
          }),
          credentials: 'include',
        })
      } else {
        // Tạo bộ thẻ mới (POST)
        res = await fetch("/api/library", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: setName,
            cards: flashcards
          }),
          credentials: 'include',
        })
      }

      if (res.ok) {
        toast.success(isUpdating ? "Đã cập nhật bộ thẻ!" : "Đã lưu vào thư viện!")
        setOriginalFlashcards([])
        setEditingSetId(null)
        setCurrentView("library")
      } else {
        throw new Error("Không thể lưu")
      }
    } catch (err) {
      toast.error("Lỗi khi lưu bộ thẻ")
    } finally {
      setIsSaving(false)
    }
  }

  const handleExportAnki = async (cardsToExport?: any[], deckName?: string) => {
    const cards = cardsToExport || flashcards
    if (cards.length === 0) {
      toast.error("Không có thẻ nào để export")
      return
    }

    const name = deckName || uploadedFile || `Flashcard AI ${new Date().toLocaleDateString("vi-VN")}`

    setIsExporting(true)
    try {
      const res = await fetch("/api/export_anki", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cards: cards,
          deck_name: name
        }),
        credentials: 'include',
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.error || "Lỗi export Anki")
      }

      // Nhận file binary → tạo link download
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${name}.apkg`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      toast.success(`Đã tải xuống ${name}.apkg`)
    } catch (err: any) {
      toast.error(err.message || "Không thể export Anki")
    } finally {
      setIsExporting(false)
    }
  }

  const handleSaveDocument = async () => {
    if (!uploadedFile || !fileUrl) {
      toast.error("Không tìm thấy thông tin tài liệu. Có thể do phiên làm việc đã hết hạn hoặc chưa tải file lên đúng cách.")
      return
    }

    setIsSavingDoc(true)
    try {
      const res = await fetch("/api/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_name: uploadedFile,
          file_url: fileUrl,
          file_size: fileSize,
          user_id: user?.user_id
        }),
        credentials: 'include',
      })

      if (res.ok) {
        setIsDocSaved(true)
        toast.success("Đã lưu tài liệu vào Thư viện!")
      } else {
        throw new Error("Lỗi lưu tài liệu")
      }
    } catch (err) {
      toast.error("Không thể lưu tài liệu")
    } finally {
      setIsSavingDoc(false)
    }
  }

  const handleStudy = (set: any) => {
    setActiveSet(set)
    setPreviousView(currentView)
    setCurrentView("study")
  }

  const handlePlay = (set: any) => {
    setActiveSet(set)
    setGameType(null)
    setPreviousView(currentView)
    setCurrentView("game")
  }

  const handleReuseDocument = (doc: any) => {
    setPreloadedDocument(doc.file_name)
    setUploadedFile(doc.file_name)
    setFileUrl(doc.file_url)
    setFileSize(doc.file_size)
    setIsDocSaved(true) // Đã có trong thư viện rồi
    setCurrentView("generator")
  }

  const handleOpenSet = (set: any) => {
    setFlashcards(set.cards || [])
    // "Khóa" bản gốc để có thể so sánh feedback khi nhấn Lưu lần nữa
    originalFlashcardsRef.current = JSON.parse(JSON.stringify(set.cards || []))
    setUploadedFile(set.name)
    setEditingSetId(set.id) // Track ID để khi lưu sẽ UPDATE thay vì INSERT
    setCurrentView("generator")
    toast.info(`Đang mở bộ thẻ: ${set.name}`)
  }

  return (
    <SidebarProvider>
      <AppSidebar currentView={currentView} onViewChange={(v) => {
        setCurrentView(v)
        if (v !== 'study' && v !== 'game') setActiveSet(null)
      }} />
      <SidebarInset>
        {/* Top Header Bar */}
        <header className="flex h-16 shrink-0 items-center gap-4 border-b border-border/60 px-6 bg-white z-50">
          <SidebarTrigger className="-ml-1" />

          {/* Page Title */}
          <h1 className="text-sm font-semibold text-foreground flex-1">
            {viewTitles[currentView] || currentView}
          </h1>

          <div className="flex items-center gap-3 ml-auto">
            <NotificationBell />

            {/* User Avatar + Dropdown */}
            <div className="relative group">
              <button className="flex items-center gap-2.5 pl-3 border-l border-border cursor-pointer hover:opacity-80 transition-opacity">
                <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center">
                  <User className="w-[18px] h-[18px] text-primary" />
                </div>
                <div className="hidden md:flex flex-col text-left">
                  <span className="text-sm font-semibold text-foreground leading-tight">{user?.name || "Người dùng"}</span>
                  <span className="text-[10px] text-primary font-medium">{user?.role === 'admin' ? 'Admin' : 'Scholar'}</span>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              </button>
              {/* Dropdown */}
              <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-xl border border-border shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 py-1">
                <div className="px-3 py-2 border-b border-border/60">
                  <p className="text-sm font-semibold text-foreground">{user?.name}</p>
                  <p className="text-xs text-muted-foreground">{user?.username}</p>
                </div>
                <button
                  onClick={() => logout()}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-500 hover:bg-red-50 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Đăng xuất
                </button>
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6 lg:p-8 bg-secondary/30">
          <div className="max-w-6xl mx-auto space-y-8">

            {/* VIEW: GENERATOR */}
            {currentView === 'generator' && (
              <section className="space-y-6">
                {/* Welcome + CTA */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold tracking-tight text-foreground">Chào mừng trở lại, {user?.name || "bạn"}! 👋</h2>
                    <p className="text-sm text-muted-foreground mt-1">Hôm nay là một ngày tuyệt vời để học hỏi và tiến bộ!</p>
                  </div>
                </div>

                <div id="generator-form-area">
                <GeneratorForm
                  onGenerate={handleGenerate}
                  isGenerating={isGenerating}
                  preloadedDocument={preloadedDocument}
                  onClearPreload={() => setPreloadedDocument(null)}
                  onSelectFromLibrary={() => setCurrentView('library')}
                  fileUrl={fileUrl}
                  fileSize={fileSize}
                  isDocSaved={isDocSaved}
                  userId={user?.user_id}
                />
                </div>

                {isGenerating && statusLogs.length > 0 && (
                  <div className="bg-white rounded-2xl p-5 border border-border shadow-card space-y-3">
                    <div className="flex items-center gap-3 pb-3 border-b border-border/60">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                        <Brain className="w-5 h-5 text-primary animate-pulse" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground">AI đang phân tích tài liệu...</p>
                        <p className="text-xs text-muted-foreground">Đang xử lý dữ liệu và tạo flashcard</p>
                      </div>
                      <div className="ml-auto">
                        <div className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      {statusLogs.map((log, i) => (
                        <div key={i} className="flex items-center gap-2.5 text-xs">
                          <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${i === statusLogs.length - 1 ? "bg-primary animate-pulse" : "bg-green-500"}`} />
                          <span className={i === statusLogs.length - 1 ? "text-foreground font-medium" : "text-muted-foreground"}>{log}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {flashcards.length > 0 && (
                  <div className="space-y-6 pt-6 border-t border-border/50 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center">
                          <LayoutGrid className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-foreground">Kết quả trích xuất</h3>
                          <p className="text-xs text-muted-foreground">AI đã tạo xong {flashcards.length} thẻ chất lượng cao.</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          onClick={() => handleExportAnki()}
                          disabled={isExporting}
                          className="gap-2 rounded-xl px-5 h-10 font-semibold transition-all hover:shadow-md"
                        >
                          {isExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                          Export Anki
                        </Button>
                        <Button
                          onClick={handleSaveToLibrary}
                          disabled={isSaving}
                          className="gap-2 rounded-xl px-6 h-10 font-semibold shadow-soft transition-all hover:shadow-md"
                        >
                          {isSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
                          {editingSetId ? "Cập nhật bộ thẻ" : "Lưu bộ thẻ"}
                        </Button>
                      </div>
                    </div>

                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
                      {flashcards.map((card, idx) => (
                        <Flashcard
                          key={idx}
                          card={card}
                          onUpdate={(q, a, n) => {
                            const newCards = [...flashcards]
                            newCards[idx] = { ...newCards[idx], question: q, answer: a, note: n }
                            setFlashcards(newCards)
                          }}
                          onDelete={() => {
                            setFlashcards(prev => prev.filter((_, i) => i !== idx))
                            toast.success("Đã xóa thẻ tạm thời")
                          }}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* VIEW: LIBRARY */}
            {currentView === 'library' && (
              <LibraryView 
                onStudy={handleStudy} 
                onPlay={handlePlay}
                onOpen={handleOpenSet}
                onReuseDocument={handleReuseDocument}
                onExportAnki={(set: any) => handleExportAnki(set.cards, set.name)}
              />
            )}

            {/* VIEW: SCHEDULE */}
            {currentView === 'schedule' && (
              <ScheduleView onStudy={handleStudy} />
            )}

            {/* VIEW: ANALYTICS */}
            {currentView === 'analytics' && (
              user?.role === 'admin' ? <AdminAnalyticsView /> : <AnalyticsView />
            )}

            {/* VIEW: STUDY */}
            {currentView === 'study' && (
              activeSet ? (
                <StudyView set={activeSet} onFinish={() => { setActiveSet(null); setCurrentView(previousView) }} />
              ) : (
                <LobbyView mode="study" onSelect={handleStudy} />
              )
            )}

            {/* VIEW: GAME */}
            {currentView === 'game' && (
              activeSet ? (
                gameType === 'matching' ? (
                  <GameView set={activeSet} onFinish={() => setGameType(null)} />
                ) : gameType === 'memory' ? (
                  <MemoryGameView set={activeSet} onFinish={() => setGameType(null)} />
                ) : (
                  /* Game Selector */
                  <div className="max-w-3xl mx-auto space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
                    <div className="text-center space-y-3">
                      <h2 className="text-4xl font-black tracking-tight flex items-center justify-center gap-3">
                        <Gamepad2 className="w-10 h-10 text-primary" />
                        Chọn trò chơi
                      </h2>
                      <p className="text-muted-foreground text-lg">Bộ thẻ: <strong>{activeSet.name}</strong> ({activeSet.cards?.length || 0} thẻ)</p>
                    </div>
                    <div className="grid gap-6 md:grid-cols-2">
                      {/* Matching Game */}
                      <button
                        onClick={() => setGameType('matching')}
                        className="group relative overflow-hidden rounded-3xl border-2 border-zinc-100 bg-white p-8 text-left shadow-xl hover:shadow-2xl hover:scale-[1.02] hover:border-primary/50 transition-all duration-500 focus:outline-none focus:ring-4 focus:ring-primary/20"
                      >
                        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-blue-100/50 to-transparent rounded-bl-full" />
                        <div className="relative space-y-4">
                          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform">
                            <Puzzle className="w-8 h-8 text-blue-600" />
                          </div>
                          <div>
                            <h3 className="text-2xl font-black text-zinc-900">Matching Game</h3>
                            <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                              Chọn từng cặp Câu hỏi - Câu trả lời tương ứng. Nhanh và chính xác để đạt điểm cao!
                            </p>
                          </div>
                          <div className="flex items-center gap-2 text-xs font-bold text-blue-600 uppercase tracking-widest">
                            <span>6 cặp</span>
                            <span className="text-zinc-300">•</span>
                            <span>Nhanh</span>
                          </div>
                        </div>
                      </button>
                      {/* Memory Game */}
                      <button
                        onClick={() => setGameType('memory')}
                        className="group relative overflow-hidden rounded-3xl border-2 border-zinc-100 bg-white p-8 text-left shadow-xl hover:shadow-2xl hover:scale-[1.02] hover:border-primary/50 transition-all duration-500 focus:outline-none focus:ring-4 focus:ring-primary/20"
                      >
                        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-emerald-100/50 to-transparent rounded-bl-full" />
                        <div className="relative space-y-4">
                          <div className="w-16 h-16 bg-emerald-100 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform">
                            <Brain className="w-8 h-8 text-emerald-600" />
                          </div>
                          <div>
                            <h3 className="text-2xl font-black text-zinc-900">Memory Game</h3>
                            <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                              Tất cả thẻ úp xuống. Lật 2 thẻ — nếu khớp Q↔A thì mở, không thì úp lại. Rèn trí nhớ!
                            </p>
                          </div>
                          <div className="flex items-center gap-2 text-xs font-bold text-emerald-600 uppercase tracking-widest">
                            <span>Toàn bộ thẻ</span>
                            <span className="text-zinc-300">•</span>
                            <span>Trí nhớ</span>
                          </div>
                        </div>
                      </button>
                    </div>
                    <div className="text-center">
                      <Button variant="ghost" onClick={() => { setActiveSet(null); setCurrentView(previousView) }} className="rounded-full text-muted-foreground">
                        ← Quay lại
                      </Button>
                    </div>
                  </div>
                )
              ) : (
                <LobbyView mode="game" onSelect={handlePlay} />
              )
            )}

            {/* FALLBACK: OTHER VIEWS */}
            {currentView === 'settings' && (
              <div className="flex flex-col items-center justify-center min-h-[400px] text-center space-y-6">
                <div className="w-24 h-24 bg-muted rounded-full flex items-center justify-center text-4xl">🚧</div>
                <div className="space-y-2">
                  <h3 className="text-2xl font-bold">Tính năng {currentView}</h3>
                  <p className="text-muted-foreground max-w-md mx-auto">
                    Chúng tôi đang làm việc chăm chỉ để hoàn thiện giao diện này bằng shadcn/ui.
                    Mọi dữ liệu vẫn đang được ghi lại ở Backend.
                  </p>
                </div>
                <Button variant="outline" onClick={() => setCurrentView('generator')} className="rounded-full">
                  Quay lại Dashboard
                </Button>
              </div>
            )}

          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
