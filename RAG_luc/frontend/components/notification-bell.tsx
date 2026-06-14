"use client"

import * as React from "react"
import { Bell, Check, Info, Zap, Award, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"

interface Notification {
  id: string
  title: string
  description: string
  type: 'info' | 'success' | 'alert'
  isRead: boolean
  createdAt: number
}

function getRelativeTime(timestamp: number) {
  const diffInMinutes = Math.floor((Date.now() - timestamp) / 60000)
  if (diffInMinutes < 1) return 'Vừa xong'
  if (diffInMinutes < 60) return `${diffInMinutes} phút trước`
  const diffInHours = Math.floor(diffInMinutes / 60)
  if (diffInHours < 24) return `${diffInHours} giờ trước`
  const diffInDays = Math.floor(diffInHours / 24)
  if (diffInDays === 1) return 'Hôm qua'
  return `${diffInDays} ngày trước`
}

export function NotificationBell() {
  const { user } = useAuth()
  const [isOpen, setIsOpen] = React.useState(false)
  const [notifications, setNotifications] = React.useState<Notification[]>([])
  const [isLoading, setIsLoading] = React.useState(true)

  // Force re-render periodically to update relative times
  const [, setTick] = React.useState(0)
  React.useEffect(() => {
    const timer = setInterval(() => setTick(t => t + 1), 60000)
    return () => clearInterval(timer)
  }, [])

  const fetchRealData = React.useCallback(async () => {
    if (!user) return

    try {
      // 1. Lấy lịch sử thông báo từ Database
      const notifRes = await fetch("/api/notifications")
      let storedNotifs: Notification[] = []
      if (notifRes.ok) {
        const data = await notifRes.json()
        if (data.notifications) {
          storedNotifs = data.notifications.map((n: any) => ({
            id: n.id,
            title: n.title,
            description: n.description,
            type: n.type,
            isRead: n.is_read,
            createdAt: new Date(n.created_at).getTime()
          }))
        }
      }

      // 2. Kiểm tra tiến trình học
      const [libRes, statsRes] = await Promise.all([
        fetch("/api/library"),
        fetch("/api/stats")
      ])

      const now = Date.now()
      const generatedNotifs: Notification[] = []

      if (libRes.ok) {
        const libData = await libRes.json()
        const sets = libData.sets || []
        
        let totalDue = 0
        sets.forEach((set: any) => {
          const dueInSet = set.cards?.filter((card: any) => {
            if (!card.srs?.due_date) return true
            return new Date(card.srs.due_date) <= new Date()
          }).length || 0
          totalDue += dueInSet
        })

        if (totalDue > 0) {
          const todayStr = new Date().toISOString().split('T')[0]
          generatedNotifs.push({
            id: `study-remind-${todayStr}`,
            title: 'Lịch học hôm nay',
            description: `Bạn đang có ${totalDue} thẻ cần ôn tập để duy trì chuỗi ghi nhớ.`,
            type: 'info',
            isRead: false,
            createdAt: now
          })
        }
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json()
        const stats = statsData.stats
        if (stats && stats.level > 1) {
          generatedNotifs.push({
            id: `level-up-${stats.level}`,
            title: 'Hạng của bạn',
            description: `Chúc mừng! Bạn đang ở Cấp độ ${stats.level} với ${stats.xp} XP.`,
            type: 'success',
            isRead: false,
            createdAt: now
          })
        }
      }

      if (generatedNotifs.length === 0 && storedNotifs.length === 0) {
        generatedNotifs.push({
          id: 'welcome-1',
          title: 'Chào mừng bạn!',
          description: 'Bắt đầu tạo bộ thẻ đầu tiên bằng AI hoặc tải lên PDF nhé.',
          type: 'info',
          isRead: false,
          createdAt: now
        })
      }

      // 3. Gộp thông báo cũ và mới
      const allNotifsMap = new Map<string, Notification>()
      storedNotifs.forEach(n => allNotifsMap.set(n.id, n))
      
      const newToSave: Notification[] = []
      generatedNotifs.forEach(n => {
        if (!allNotifsMap.has(n.id)) {
          allNotifsMap.set(n.id, n)
          newToSave.push(n) // Đánh dấu các thông báo vừa được tạo mới để lưu lên DB
        }
      })

      const finalNotifs = Array.from(allNotifsMap.values())
        .sort((a, b) => b.createdAt - a.createdAt)
        .slice(0, 20)

      setNotifications(finalNotifs)

      // 4. Lưu những thông báo mới tạo lên DB
      if (newToSave.length > 0) {
        fetch("/api/notifications", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notifications: newToSave })
        })
      }

    } catch (err) {
      console.error("Failed to fetch notifications:", err)
    } finally {
      setIsLoading(false)
    }
  }, [user])

  React.useEffect(() => {
    fetchRealData()
    const interval = setInterval(fetchRealData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [fetchRealData])

  const unreadCount = notifications.filter(n => !n.isRead).length

  const markAsRead = async (id: string) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, isRead: true } : n))
    fetch(`/api/notifications/${id}/read`, { method: "PUT" })
  }

  const markAllAsRead = async () => {
    setNotifications(prev => prev.map(n => ({ ...n, isRead: true })))
    fetch(`/api/notifications/read_all`, { method: "PUT" })
  }

  const deleteNotification = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setNotifications(prev => prev.filter(n => n.id !== id))
    fetch(`/api/notifications/${id}`, { method: "DELETE" })
  }


  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        className="relative rounded-full hover:bg-primary/10 transition-all group w-12 h-12"
        onClick={() => setIsOpen(!isOpen)}
      >
        <Bell className="w-7 h-7 text-zinc-700 group-hover:text-primary transition-colors stroke-[2.5px]" />
        {unreadCount > 0 && (
          <span className="absolute top-2 right-2 w-[18px] h-[18px] bg-red-500 text-white text-[9px] font-black flex items-center justify-center rounded-full border-2 border-white shadow-sm animate-in zoom-in duration-300">
            {unreadCount}
          </span>
        )}
      </Button>

      {isOpen && (
        <>
          <div 
            className="fixed inset-0 z-40" 
            onClick={() => setIsOpen(false)} 
          />
          <div className="absolute right-0 mt-3 w-80 md:w-96 bg-white rounded-[2rem] shadow-2xl border border-border/50 z-[100] overflow-hidden animate-in fade-in slide-in-from-top-4 duration-300">
            <div className="p-6 border-b border-border/50 flex items-center justify-between bg-zinc-50/50">
              <div className="space-y-1">
                <h3 className="font-black text-xl tracking-tight">Thông báo</h3>
                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                  Bạn có {unreadCount} thông báo mới
                </p>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                className="text-[10px] font-bold uppercase tracking-widest hover:text-primary"
                onClick={markAllAsRead}
              >
                Đánh dấu tất cả
              </Button>
            </div>

            <ScrollArea className="h-[400px]">
              <div className="divide-y divide-border/30">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 text-center px-10">
                    <div className="bg-muted/30 p-4 rounded-full mb-4">
                       <Check className="w-8 h-8 text-muted-foreground/30" />
                    </div>
                    <p className="text-muted-foreground font-medium">Bạn không có thông báo nào!</p>
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      className={cn(
                        "p-5 transition-all cursor-pointer hover:bg-muted/30 relative group",
                        !n.isRead && "bg-primary/[0.02]"
                      )}
                      onClick={() => markAsRead(n.id)}
                    >
                      {!n.isRead && (
                         <div className="absolute top-6 left-2 w-1.5 h-1.5 bg-primary rounded-full" />
                      )}
                      <div className="flex gap-4">
                        <div className={cn(
                          "w-10 h-10 shrink-0 rounded-2xl flex items-center justify-center",
                          n.type === 'info' && "bg-blue-50 text-blue-500",
                          n.type === 'success' && "bg-green-50 text-green-500",
                          n.type === 'alert' && "bg-orange-50 text-orange-500"
                        )}>
                          {n.type === 'info' && <Info className="w-5 h-5" />}
                          {n.type === 'success' && <Award className="w-5 h-5" />}
                          {n.type === 'alert' && <Zap className="w-5 h-5" />}
                        </div>
                        <div className="flex-1 space-y-1">
                          <div className="flex justify-between items-start">
                            <h4 className={cn("text-sm font-bold", !n.isRead ? "text-zinc-900" : "text-zinc-500")}>
                              {n.title}
                            </h4>
                            <span className="text-[10px] font-medium text-muted-foreground">
                              {getRelativeTime(n.createdAt)}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                            {n.description}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-full opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500 transition-all"
                          onClick={(e) => deleteNotification(n.id, e)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
            
            <div className="p-4 bg-muted/20 text-center border-t border-border/30">
               <Button variant="link" className="text-xs font-bold uppercase tracking-widest text-muted-foreground hover:text-primary no-underline">
                  Xem lịch sử thông báo
               </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

