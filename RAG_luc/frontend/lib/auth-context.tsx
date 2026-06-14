"use client"

import * as React from "react"
import { toast } from "sonner"

interface User {
  username: string
  user_id: string
  role: string
  name: string
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<boolean>
  register: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)

  const checkAuth = React.useCallback(async () => {
    try {
      const res = await fetch("/api/me", { credentials: 'include' })
      const data = await res.json()
      if (data.logged_in) {
        setUser({
          username: data.username,
          user_id: data.user_id,
          role: data.role,
          name: data.name
        })
      } else {
        setUser(null)
      }
    } catch (err) {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  React.useEffect(() => {
    checkAuth()
  }, [checkAuth])

  const login = async (username: string, password: string) => {
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      })
      const data = await res.json()
      if (res.ok && data.success) {
        await checkAuth()
        toast.success(`Chào mừng trở lại, ${data.name}!`)
        return true
      } else {
        toast.error(data.error || "Sai tài khoản hoặc mật khẩu")
        return false
      }
    } catch (err) {
      toast.error("Lỗi kết nối máy chủ")
      return false
    }
  }

  const register = async (username: string, password: string) => {
    try {
      const res = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      })
      const data = await res.json()
      if (res.ok && data.success) {
        toast.success("Đăng ký thành công! Hãy đăng nhập.")
        return true
      } else {
        toast.error(data.error || "Không thể đăng ký")
        return false
      }
    } catch (err) {
      toast.error("Lỗi kết nối máy chủ")
      return false
    }
  }

  const logout = async () => {
    try {
      await fetch("/api/logout", { method: "POST", credentials: 'include' })
      setUser(null)
      toast.success("Đã đăng xuất")
    } catch (err) {
      toast.error("Lỗi khi đăng xuất")
    }
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = React.useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
