"use client"

import * as React from "react"
import {
  Brain,
  Home,
  FileText,
  Layers,
  Calendar,
  TrendingUp,
  Settings,
  LogOut,
  User,
  ChevronLeft,
  Crown,
  ArrowRight,
  BookOpen,
  Gamepad2,
  BarChart3,
  Library,
  Sparkles,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupContent,
} from "@/components/ui/sidebar"

const navItems = [
  { title: "Tạo thẻ", icon: Sparkles, id: "generator" },
  { title: "Thư viện", icon: Library, id: "library" },
  { title: "Thống kê", icon: BarChart3, id: "analytics" },
  { title: "Lịch ôn tập", icon: Calendar, id: "schedule" },
  { title: "Học tập", icon: BookOpen, id: "study" },
  { title: "Trò chơi", icon: Gamepad2, id: "game" },
]

export function AppSidebar({ 
  currentView, 
  onViewChange 
}: { 
  currentView: string;
  onViewChange: (view: string) => void;
}) {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = React.useState(false)

  return (
    <Sidebar className="border-r border-border/60 bg-white">
      {/* Header */}
      <SidebarHeader className="h-16 flex items-center px-5 border-b border-border/60">
        <div className="flex items-center gap-3 w-full">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center flex-shrink-0">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-foreground">Flashcard AI</span>
        </div>
      </SidebarHeader>

      {/* Navigation */}
      <SidebarContent className="px-3 py-4">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="space-y-1">
              {navItems.map((item) => {
                const isActive = currentView === item.id
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      isActive={isActive}
                      onClick={() => onViewChange(item.id)}
                      className={`w-full justify-start gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 ${
                        isActive
                          ? "bg-primary/8 text-primary font-semibold"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      }`}
                    >
                      <item.icon className={`w-[18px] h-[18px] flex-shrink-0 ${isActive ? "text-primary" : ""}`} />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>


    </Sidebar>
  )
}
