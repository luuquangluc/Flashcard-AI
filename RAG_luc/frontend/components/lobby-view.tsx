"use client"

import * as React from "react"
import { 
  Play, 
  Gamepad2, 
  Layers, 
  Search, 
  Loader2,
  Trophy,
  BookOpen,
  ArrowRight
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"

interface LobbyViewProps {
  mode: 'study' | 'game'
  onSelect: (set: any) => void
}

export function LobbyView({ mode, onSelect }: LobbyViewProps) {
  const [sets, setSets] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(true)
  const [searchQuery, setSearchQuery] = React.useState("")

  React.useEffect(() => {
    const fetchSets = async () => {
      try {
        const response = await fetch("/api/library")
        if (response.ok) {
          const data = await response.json()
          setSets(data.sets || [])
        }
      } catch (error) {
        toast.error("Không thể tải danh sách bộ thẻ")
      } finally {
        setLoading(false)
      }
    }
    fetchSets()
  }, [])

  const filteredSets = sets.filter(s => 
    (s.name || s.title || "").toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
        <p className="text-muted-foreground font-medium animate-pulse uppercase tracking-widest text-xs">Đang mở cửa sảnh...</p>
      </div>
    )
  }

  return (
    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <h2 className="text-4xl font-black tracking-tight flex items-center gap-3">
            {mode === 'study' ? (
              <>
                <BookOpen className="w-10 h-10 text-primary" />
                Sảnh Ôn Tập
              </>
            ) : (
              <>
                <Gamepad2 className="w-10 h-10 text-primary" />
                Sảnh Trò Chơi
              </>
            )}
          </h2>
          <p className="text-muted-foreground text-lg">
            {mode === 'study' 
              ? "Chọn một bộ thẻ để bắt đầu hành trình ghi nhớ." 
              : "Thử thách trí nhớ của bạn với các trò chơi tương tác."}
          </p>
        </div>
        <div className="relative w-full md:w-96">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input 
            placeholder="Tìm kiếm bộ thẻ của bạn..." 
            className="pl-12 h-12 bg-white shadow-lg border-none rounded-2xl"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {filteredSets.length === 0 ? (
        <Card className="border-none bg-secondary/30 rounded-[2rem] overflow-hidden">
          <CardContent className="flex flex-col items-center justify-center py-24 text-center">
            <div className="bg-background p-6 rounded-full mb-6 shadow-xl">
               <Layers className="w-12 h-12 text-muted-foreground/30" />
            </div>
            <h3 className="text-2xl font-bold">Thư viện đang trống</h3>
            <p className="text-muted-foreground max-w-sm mt-2">
              Bạn cần có ít nhất một bộ thẻ trong thư viện để bắt đầu {mode === 'study' ? 'ôn tập' : 'chơi'}.
            </p>
            <Button className="mt-8 rounded-full px-8 py-6 font-bold text-lg" onClick={() => window.location.reload()}>
               Tạo bộ thẻ đầu tiên
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {filteredSets.map((set) => (
            <Card key={set.id} className="group hover:scale-[1.02] transition-all duration-500 border-none shadow-xl bg-white rounded-[2rem] overflow-hidden flex flex-col h-full">
              <CardHeader className="pb-4 pt-8 px-8">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-3 rounded-2xl bg-primary/10 text-primary">
                    {mode === 'study' ? <Play className="w-6 h-6 fill-current" /> : <Gamepad2 className="w-6 h-6" />}
                  </div>
                  <Badge variant="secondary" className="font-black px-3 py-1 rounded-full text-xs">
                    {set.cards?.length || 0} CARDS
                  </Badge>
                </div>
                <CardTitle className="text-2xl font-black leading-tight group-hover:text-primary transition-colors line-clamp-2">
                   {set.name}
                </CardTitle>
                <CardDescription className="text-xs font-bold uppercase tracking-widest mt-2 flex items-center gap-2">
                   <Trophy className="w-3.5 h-3.5 text-yellow-500" />
                   {set.last_review ? `Học lần cuối: ${new Date(set.last_review).toLocaleDateString("vi-VN")}` : "Chưa từng học"}
                </CardDescription>
              </CardHeader>
              <CardFooter className="p-8 pt-4">
                <Button 
                  className="w-full gap-3 h-14 rounded-2xl font-black text-lg shadow-xl shadow-primary/20 transition-all"
                  onClick={() => onSelect(set)}
                >
                  BẮT ĐẦU NGAY
                  <ArrowRight className="w-5 h-5" />
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
