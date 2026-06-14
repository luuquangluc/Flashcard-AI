"use client"

import * as React from "react"
import { Upload, Sparkles, FileText, Languages, X, Loader2, CheckCircle2, Settings2, BookOpen, Quote, Video, Play } from "lucide-react"
import { Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"

interface GeneratorFormProps {
  onGenerate: (payload: any) => void
  isGenerating: boolean
  preloadedDocument?: string | null
  onClearPreload?: () => void
  onSelectFromLibrary?: () => void
  fileUrl?: string | null
  fileSize?: number
  isDocSaved?: boolean
  userId?: string
}

export function GeneratorForm({ 
  onGenerate, 
  isGenerating, 
  preloadedDocument, 
  onClearPreload, 
  onSelectFromLibrary,
  fileUrl: propFileUrl,
  fileSize: propFileSize,
  isDocSaved: propIsDocSaved,
  userId
}: GeneratorFormProps) {
  const [inputText, setInputText] = React.useState("")
  const [mode, setMode] = React.useState("topic") // topic | page | youtube
  const [desireMode, setDesireMode] = React.useState("content") // content | language
  const [numCards, setNumCards] = React.useState(5)
  const [isUploading, setIsUploading] = React.useState(false)
  const [uploadedFile, setUploadedFile] = React.useState<string | null>(null)
  const [fileUrl, setFileUrl] = React.useState<string | null>(propFileUrl || null)
  const [fileSize, setFileSize] = React.useState<number>(propFileSize || 0)
  const [isRAGInitialized, setIsRAGInitialized] = React.useState(false)
  const [isSavingDoc, setIsSavingDoc] = React.useState(false)
  const [isDocSaved, setIsDocSaved] = React.useState(propIsDocSaved || false)
  const [isTranscribing, setIsTranscribing] = React.useState(false)
  const [youtubeUrl, setYoutubeUrl] = React.useState("")
  
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const videoFileInputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (preloadedDocument) {
      setUploadedFile(preloadedDocument)
      setFileUrl(propFileUrl || null)
      setFileSize(propFileSize || 0)
      setIsRAGInitialized(true)
      setIsDocSaved(propIsDocSaved ?? true)
      setMode("page")
      onClearPreload?.()
    }
  }, [preloadedDocument, onClearPreload, propFileUrl, propFileSize, propIsDocSaved])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Chỉ hỗ trợ file PDF cho tính năng RAG.")
      return
    }

    // Lưu file gốc vào IndexedDB để dùng cho chế độ tập trung
    try {
      const { saveFile } = await import("@/lib/idb")
      await saveFile(`original_pdf_${file.name}`, file)
    } catch (e_idb) {
      console.error("Lỗi lưu file gốc vào IndexedDB:", e_idb)
    }

    const formData = new FormData()
    formData.append("file", file)
    if (userId) {
      formData.append("user_id", userId)
    }

    setIsUploading(true)
    setIsRAGInitialized(false)

    try {
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
        credentials: 'include',
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || "Lỗi xử lý file")
      }

      setUploadedFile(file.name)
      setFileUrl(data.file_url)
      setFileSize(data.file_size)
      setIsRAGInitialized(true)
      setIsDocSaved(false)
      
      if (!data.file_url) {
        if (!data.uid) {
          toast.warning("Tài liệu đã được xử lý nhưng không thể lưu vào thư viện vì bạn chưa đăng nhập.")
        } else {
          toast.warning("Tài liệu đã được xử lý nhưng gặp lỗi khi tải lên bộ nhớ đám mây (Supabase).")
        }
      } else {
        toast.success(`Đã tải tài liệu: ${file.name}`)
      }
    } catch (error: any) {
      toast.error(error.message)
      console.error("Upload error:", error)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  const handleVideoFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const validTypes = ["video/", "audio/"]
    const isValid = validTypes.some(type => file.type.startsWith(type))
    if (!isValid) {
      toast.error("Vui lòng chọn file video hoặc audio.")
      return
    }

    const formData = new FormData()
    formData.append("file", file)
    if (userId) {
      formData.append("user_id", userId)
    }
    formData.append("title", file.name)

    setIsTranscribing(true)
    setYoutubeUrl(file.name)

    try {
      toast.info("Đang tải file lên và xử lý, quá trình này có thể mất vài phút...")
      const response = await fetch("/api/video/upload", {
        method: "POST",
        body: formData,
        credentials: 'include',
      })

      const text = await response.text()
      let data
      try {
        data = JSON.parse(text)
      } catch (e) {
        throw new Error("Lỗi hệ thống (Phản hồi không phải JSON)")
      }

      if (!response.ok) {
        throw new Error(data.error || "Lỗi xử lý video upload")
      }

      setUploadedFile(data.title)
      setFileUrl(data.file_url)
      setFileSize(data.file_size)
      setIsRAGInitialized(true)
      setMode("page")
      
      toast.success(`Đã xử lý video: ${data.title}`)
    } catch (error: any) {
      toast.error(error.message)
      console.error("Video upload error:", error)
      setYoutubeUrl("")
    } finally {
      setIsTranscribing(false)
      if (videoFileInputRef.current) videoFileInputRef.current.value = ""
    }
  }

  const handleRemoveFile = async () => {
    setUploadedFile(null)
    setIsRAGInitialized(false)
    setMode("topic")
    setInputText("")
    
    try {
      await fetch("/api/clear_rag", { method: "POST" })
    } catch (e) {
      console.error("Failed to clear RAG state:", e)
    }
    
    toast.info("Đã gỡ bỏ tài liệu. Chuyển sang chế độ AI chung.")
  }

  const handleSaveDocument = async () => {
    if (!uploadedFile || !fileUrl) {
      toast.error("Không tìm thấy thông tin tài liệu để lưu. Vui lòng thử tải lại file.")
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
          user_id: userId
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

  const handleTranscribeVideo = async () => {
    if (!youtubeUrl.trim()) {
      toast.error("Vui lòng nhập link video.")
      return
    }

    setIsTranscribing(true)
    try {
      const res = await fetch("/api/video/transcribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          url: youtubeUrl.trim(),
          user_id: userId 
        }),
        credentials: 'include',
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.error || "Lỗi xử lý video")
      }

      const reader = res.body?.getReader()
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
                toast.info(data.content)
              } else if (data.type === "result") {
                toast.success(`Đã trích xuất xong: ${data.title}`)
                setUploadedFile(data.title)
                setFileUrl(data.file_url)
                setFileSize(data.file_size || 0)
                setIsRAGInitialized(true)
                setIsDocSaved(false)
                setYoutubeUrl("")
              } else if (data.type === "error") {
                throw new Error(data.content)
              }
            } catch (e: any) {
              console.error("Lỗi parse SSE:", e)
            }
          }
        }
      }
    } catch (err: any) {
      toast.error(err.message)
    } finally {
      setIsTranscribing(false)
    }
  }

  const handleGenerateClick = () => {
    // Nếu chọn chế độ dải trang thì bắt buộc phải nhập dải trang
    if (mode === "page" && !inputText.trim()) {
      toast.error("Vui lòng nhập dải trang (ví dụ: 1-5).")
      return
    }

    // Nếu chưa có file mà cũng không nhập text thì mới báo lỗi
    if (!inputText.trim() && !uploadedFile && !preloadedDocument) {
      toast.error("Vui lòng nhập chủ đề.")
      return
    }

    let desireValue = ""
    if (desireMode === "language") {
      desireValue = "[MODE_LANGUAGE] Tập trung trích xuất các từ vựng, cụm từ hoặc thuật ngữ mới từ văn bản. Bạn chỉ cần cung cấp từ/cụm từ gốc trong phần câu hỏi."
    }

    const payload: any = {
      num_cards: numCards,
      user_desire: desireValue,
      mode,
      desire: desireMode,
      fileName: uploadedFile || preloadedDocument,
      fileUrl: fileUrl,
      fileSize: fileSize,
      isSaved: isDocSaved
    }

    if (mode === "topic") {
      payload.query = inputText
      payload.page_range = ""
    } else {
      payload.query = ""
      payload.page_range = inputText
    }

    onGenerate(payload)
  }

  return (
    <Card className="p-6 shadow-notion border-border/50 space-y-8 bg-white/50 backdrop-blur-sm">
      <input 
        type="file" 
        ref={videoFileInputRef} 
        className="hidden" 
        accept="video/*,audio/*" 
        onChange={handleVideoFileChange}
      />
      <div className="flex flex-col md:flex-row gap-6 items-start md:items-center justify-between border-b border-border/50 pb-6">
        <div className="space-y-3 w-full md:w-auto">
          <Label className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
            <Settings2 className="w-3.5 h-3.5" />
            Phương thức trích xuất
          </Label>
          <Tabs value={mode} className="w-full md:w-[320px]" onValueChange={setMode}>
            <TabsList className="grid grid-cols-2 bg-muted/50">
              <TabsTrigger value="topic" className="gap-2">
                <Sparkles className="w-3.5 h-3.5" />
                Chủ đề
              </TabsTrigger>
              <TabsTrigger value="page" className="gap-2">
                <FileText className="w-3.5 h-3.5" />
                Dải trang
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="space-y-3 w-full md:w-auto">
          <Label className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
            <BookOpen className="w-3.5 h-3.5" />
            Chế độ AI
          </Label>
          <Tabs value={desireMode} className="w-full md:w-[320px]" onValueChange={setDesireMode}>
            <TabsList className="grid grid-cols-2 bg-muted/50">
              <TabsTrigger value="content" className="gap-2">
                <Quote className="w-3.5 h-3.5" />
                Nội dung
              </TabsTrigger>
              <TabsTrigger value="language" className="gap-2">
                <Languages className="w-3.5 h-3.5" />
                Từ vựng
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="space-y-3 w-full md:w-24">
          <Label className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
            Số thẻ
          </Label>
          <Input 
            type="number" 
            min={1} 
            max={20} 
            value={isNaN(numCards) ? "" : numCards} 
            onChange={(e) => {
              const val = parseInt(e.target.value);
              setNumCards(isNaN(val) ? 0 : val);
            }}
            className="bg-muted/50 border-none font-bold text-center"
          />
        </div>
      </div>

      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
           <Label className="text-sm font-semibold">Nguồn tài liệu</Label>
           <div className="flex flex-wrap items-center gap-2 justify-end">
            <input 
              type="file" 
              ref={fileInputRef} 
              className="hidden" 
              accept=".pdf" 
              onChange={handleFileChange}
            />
            
            <div className="flex items-center gap-1 bg-muted/30 border border-border/50 rounded-md px-1 h-8 focus-within:ring-1 focus-within:ring-primary/30 transition-all">
              <Video className="w-3 h-3 ml-1 text-muted-foreground" />
              <button 
                type="button"
                className="p-1 hover:bg-muted rounded-sm"
                onClick={() => videoFileInputRef.current?.click()}
                disabled={isTranscribing || isGenerating}
                title="Tải lên file video/audio"
              >
                <Upload className="w-3 h-3 text-muted-foreground hover:text-foreground" />
              </button>
              <input 
                type="text" 
                placeholder="Link video..." 
                className="bg-transparent border-none text-[11px] w-[110px] md:w-[130px] focus:outline-none px-2 h-full placeholder:text-muted-foreground/70"
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                disabled={isTranscribing || isGenerating}
                onKeyDown={(e) => e.key === 'Enter' && handleTranscribeVideo()}
              />
              <Button 
                variant="default"
                size="sm" 
                className="h-6 px-2 text-[10px] rounded-sm" 
                onClick={handleTranscribeVideo} 
                disabled={!youtubeUrl || isTranscribing}
              >
                {isTranscribing ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <span>Tải</span>
                )}
              </Button>
            </div>

            <Button 
              variant="outline" 
              size="sm"
              className="gap-2 border-dashed h-8 px-3 text-xs"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading || isGenerating}
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>Đang tải...</span>
                </>
              ) : (
                <>
                  <Upload className="w-3 h-3" />
                  <span>Tải lên PDF</span>
                </>
              )}
            </Button>
            <Button 
              variant="secondary" 
              size="sm"
              className="gap-2 h-8 px-3 text-xs"
              onClick={onSelectFromLibrary}
              disabled={isUploading || isGenerating}
            >
              <BookOpen className="w-3 h-3" />
              Thư viện
            </Button>
          </div>
        </div>

        {uploadedFile && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 p-3 bg-primary/5 border border-primary/10 rounded-xl animate-in zoom-in-95">
              <div className="bg-primary/20 p-2 rounded-lg">
                 <FileText className="w-4 h-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                 <p className="text-sm font-bold truncate">{uploadedFile}</p>
                 <p className="text-[10px] text-primary font-bold uppercase tracking-widest flex items-center gap-1">
                   <CheckCircle2 className="w-3 h-3" /> Tài liệu đã sẵn sàng
                 </p>
              </div>
              {!isGenerating && (
                <div className="flex items-center gap-1">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className={`h-8 px-2 text-[10px] font-bold ${isDocSaved ? 'text-green-600 bg-green-50' : 'text-primary hover:bg-primary/10'}`}
                    onClick={handleSaveDocument}
                    disabled={isSavingDoc || isDocSaved}
                  >
                    {isSavingDoc ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin mr-1" />
                        <span>ĐANG LƯU...</span>
                      </>
                    ) : isDocSaved ? (
                      <>
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                        <span>ĐÃ LƯU</span>
                      </>
                    ) : (
                      <>
                        <Save className="w-3 h-3 mr-1" />
                        <span>LƯU</span>
                      </>
                    )}
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-destructive/10 hover:text-destructive" onClick={handleRemoveFile}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="space-y-4">
          <div className="relative group">
            <Input 
              placeholder={
                mode === "topic" ? "Bạn muốn tạo thẻ về chủ đề gì?" : "Ví dụ: 1-5, 10, 12-15"
              }
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isGenerating || isTranscribing}
              className="text-lg py-8 px-6 bg-zinc-100/50 border-transparent shadow-none focus-visible:ring-2 focus-visible:ring-primary/20 transition-all rounded-2xl"
            />
            <div className="absolute right-4 top-1/2 -translate-y-1/2">
               <div className="bg-white/80 p-2 rounded-xl shadow-sm border border-border/50 text-[10px] font-bold text-muted-foreground uppercase tracking-widest pointer-events-none flex items-center gap-2">
                  {mode}
               </div>
            </div>
          </div>
          
          <div className="flex items-center justify-center pt-4">
               <Button 
                 onClick={handleGenerateClick} 
                 disabled={isGenerating || isUploading}
                 className="rounded-full px-12 py-7 text-lg font-black shadow-xl shadow-primary/20 transition-all hover:scale-[1.05] active:scale-95 min-w-[300px] gap-3"
               >
                 {isGenerating ? (
                   <span className="flex items-center gap-3">
                     <Loader2 className="w-6 h-6 animate-spin" />
                     <span>Đang xử lý...</span>
                   </span>
                 ) : (
                   <span className="flex items-center gap-3">
                     <Sparkles className="w-6 h-6" />
                     <span>Generate Flashcard</span>
                   </span>
                 )}
               </Button>
          </div>
          
          <p className="text-center text-xs text-muted-foreground">
             AI sẽ trích xuất {numCards} thẻ ở chế độ {desireMode === 'content' ? 'Nội dung' : 'Từ vựng'} 
             {isRAGInitialized ? ` dựa trên file ${uploadedFile}` : ''}.
          </p>
        </div>
      </div>
    </Card>
  )
}
