"use client"

import * as React from "react"
import { 
  FileText, 
  Trash2, 
  Play, 
  Gamepad2, 
  Calendar, 
  ExternalLink,
  Clock,
  Layers,
  Search,
  MoreVertical,
  Loader2,
  Sparkles,
  Eye,
  Download
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"
import { ScrollArea } from "@/components/ui/scroll-area"

interface LibraryViewProps {
  onStudy: (set: any) => void
  onPlay: (set: any) => void
  onOpen: (set: any) => void
  onReuseDocument?: (doc: any) => void
  onExportAnki?: (set: any) => void
}

export function LibraryView({ onStudy, onPlay, onOpen, onReuseDocument, onExportAnki }: LibraryViewProps) {
  const [documents, setDocuments] = React.useState<any[]>([])
  const [sets, setSets] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(true)
  const [searchQuery, setSearchQuery] = React.useState("")

  const loadLibrary = React.useCallback(async () => {
    setLoading(true)
    try {
      const [docsRes, setsRes] = await Promise.all([
        fetch("/api/documents", { credentials: 'include' }),
        fetch("/api/library", { credentials: 'include' })
      ])
      
      if (docsRes.ok) {
        const data = await docsRes.json()
        setDocuments(data.documents || [])
      }
      
      if (setsRes.ok) {
        const data = await setsRes.json()
        setSets(data.sets || [])
      }
    } catch (error) {
      console.error("Lỗi tải thư viện:", error)
      toast.error("Không thể tải dữ liệu thư viện")
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadLibrary()
  }, [loadLibrary])

  const handleDeleteSet = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm("Bạn có chắc chắn muốn xóa bộ thẻ này?")) return

    try {
      const res = await fetch(`/api/library/${id}`, { method: "DELETE", credentials: 'include' })
      if (res.ok) {
        toast.success("Đã xóa bộ thẻ")
        loadLibrary()
      } else {
        throw new Error("Lỗi khi xóa")
      }
    } catch (err) {
      toast.error("Không thể xóa bộ thẻ")
    }
  }

  const handleDeleteDocument = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm("Bạn có chắc chắn muốn xóa tài liệu này?")) return

    try {
      const res = await fetch(`/api/documents/${id}`, { method: "DELETE", credentials: 'include' })
      if (res.ok) {
        toast.success("Đã xóa tài liệu")
        loadLibrary()
      } else {
        throw new Error("Lỗi khi xóa")
      }
    } catch (err) {
      toast.error("Không thể xóa tài liệu")
    }
  }

  const handleReuseDocument = async (doc: any) => {
    toast.info("Đang nạp lại tài liệu...")
    try {
      const res = await fetch("/api/documents/reuse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: doc.file_url }),
        credentials: 'include',
      })

      if (res.ok) {
        const data = await res.json()
        toast.success(`Đã nạp ${data.chunks} đoạn kiến thức từ ${doc.file_name}`)
        // Gọi callback để chuyển tab và set file preloaded
        if (onReuseDocument) {
          onReuseDocument(doc)
        }
      } else {
        const err = await res.json()
        throw new Error(err.error || "Không thể tái sử dụng tài liệu")
      }
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  const filteredSets = sets.filter(s => 
    (s.name || s.title || "").toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredDocs = documents.filter(d => 
    d.file_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
        <p className="text-muted-foreground font-medium animate-pulse uppercase tracking-widest text-xs">Đang truy xuất thư viện...</p>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-black tracking-tight">Thư viện của bạn</h2>
          <p className="text-muted-foreground">Quản lý tài liệu và bộ thẻ đã lưu trữ.</p>
        </div>
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input 
            placeholder="Tìm kiếm tài liệu, bộ thẻ..." 
            className="pl-10 bg-muted/30 border-none rounded-full"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <Tabs defaultValue="sets" className="w-full">
        <TabsList className="bg-muted/50 p-1 mb-6">
          <TabsTrigger value="sets" className="gap-2 px-6">
            <Layers className="w-4 h-4" />
            Bộ thẻ Flashcard
          </TabsTrigger>
          <TabsTrigger value="docs" className="gap-2 px-6">
            <FileText className="w-4 h-4" />
            Tài liệu
          </TabsTrigger>
        </TabsList>

        <TabsContent value="sets">
          {filteredSets.length === 0 ? (
            <Card className="border-dashed bg-muted/10">
              <CardContent className="flex flex-col items-center justify-center py-20 text-center">
                <Layers className="w-12 h-12 text-muted-foreground/30 mb-4" />
                <h3 className="text-lg font-bold">Chưa có bộ thẻ nào</h3>
                <p className="text-sm text-muted-foreground max-w-xs mt-1">
                  Hãy bắt đầu tạo flashcard từ tài liệu của bạn và lưu chúng lại đây.
                </p>
                <Button variant="outline" className="mt-6 rounded-full" onClick={() => window.location.reload()}>
                   Tạo ngay
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {filteredSets.map((set) => (
                <Card key={set.id} className="group hover:shadow-xl transition-all duration-300 border-border/50 overflow-hidden flex flex-col h-full">
                  <CardHeader className="pb-4">
                    <div className="flex justify-between items-start">
                      <div className="bg-primary/10 p-2 rounded-lg">
                        <Layers className="w-5 h-5 text-primary" />
                      </div>
                      <Badge variant="secondary" className="font-bold">
                        {set.cards?.length || 0} thẻ
                      </Badge>
                    </div>
                    <CardTitle className="mt-4 line-clamp-1">{set.name}</CardTitle>
                    <CardDescription className="flex items-center gap-2 text-[10px] uppercase font-bold tracking-wider">
                      <Calendar className="w-3 h-3" />
                      {new Date(set.created_at).toLocaleDateString("vi-VN")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1">
                     <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <Clock className="w-3.5 h-3.5" />
                        <span>Ôn tập gần nhất: {set.last_review ? new Date(set.last_review).toLocaleDateString("vi-VN") : "Chưa ôn tập"}</span>
                     </div>
                  </CardContent>
                  <CardFooter className="bg-muted/30 p-4 gap-2">
                    <Button 
                      className="flex-1 gap-2 rounded-full font-bold shadow-md shadow-primary/10"
                      onClick={() => onStudy(set)}
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      Học
                    </Button>
                    <Button 
                      variant="outline" 
                      className="w-12 h-10 p-0 rounded-full hover:bg-primary/5 hover:text-primary transition-colors"
                      onClick={() => onOpen(set)}
                      title="Mở bộ thẻ để sửa/xóa"
                    >
                      <Eye className="w-5 h-5" />
                    </Button>
                    <Button 
                      variant="outline" 
                      className="w-12 h-10 p-0 rounded-full hover:bg-primary/5 hover:text-primary transition-colors"
                      onClick={() => onPlay(set)}
                    >
                      <Gamepad2 className="w-5 h-5" />
                    </Button>
                    {onExportAnki && (
                      <Button 
                        variant="outline" 
                        className="w-12 h-10 p-0 rounded-full hover:bg-emerald-50 hover:text-emerald-600 transition-colors"
                        onClick={(e) => { e.stopPropagation(); onExportAnki(set) }}
                        title="Export ra file Anki (.apkg)"
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                    )}
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-10 w-10 rounded-full hover:bg-destructive/10 hover:text-destructive"
                      onClick={(e) => handleDeleteSet(set.id, e)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="docs">
           <div className="grid gap-4">
              {filteredDocs.length === 0 ? (
                 <div className="text-center py-20 bg-muted/10 rounded-2xl border-dashed border-2 border-border">
                    <FileText className="w-12 h-12 mx-auto text-muted-foreground/30 mb-4" />
                    <p className="text-muted-foreground">Bạn chưa tải lên tài liệu nào.</p>
                 </div>
              ) : (
                filteredDocs.map((doc) => (
                  <Card key={doc.id} className="flex items-center p-4 hover:bg-muted/20 transition-colors cursor-default border-border/40">
                    <div className="bg-zinc-100 p-3 rounded-xl mr-4">
                      <FileText className="w-6 h-6 text-zinc-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-bold truncate">{doc.file_name}</h4>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                        <span>{(doc.file_size / 1024 / 1024).toFixed(2)} MB</span>
                        <span>•</span>
                        <span>{new Date(doc.created_at).toLocaleDateString("vi-VN")}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                       <Button variant="outline" size="sm" className="rounded-full gap-2 text-xs font-bold" onClick={() => handleReuseDocument(doc)}>
                          <Sparkles className="w-3.5 h-3.5" />
                          Sử dụng
                       </Button>
                       <Button variant="ghost" size="icon" className="rounded-full" asChild>
                          <a href={doc.file_url} target="_blank" rel="noreferrer">
                            <ExternalLink className="w-4 h-4" />
                          </a>
                       </Button>
                       <Button variant="ghost" size="icon" className="rounded-full text-destructive hover:bg-destructive/10" onClick={(e) => handleDeleteDocument(doc.id, e)}>
                          <Trash2 className="w-4 h-4" />
                       </Button>
                    </div>
                  </Card>
                ))
              )}
           </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
