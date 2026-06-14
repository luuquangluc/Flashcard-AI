"use client"

import * as React from "react"
import { Brain, User, Lock, Eye, EyeOff, Sparkles, Upload, BarChart3, ArrowRight } from "lucide-react"
import { useAuth } from "@/lib/auth-context"

export function AuthView() {
  const { login, register } = useAuth()
  const [isLogin, setIsLogin] = React.useState(true)
  const [showPassword, setShowPassword] = React.useState(false)
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [confirmPassword, setConfirmPassword] = React.useState("")
  const [name, setName] = React.useState("")
  const [loading, setLoading] = React.useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) return

    if (!isLogin && password !== confirmPassword) {
      alert("Mật khẩu xác nhận không khớp!")
      return
    }

    setLoading(true)
    try {
      if (isLogin) {
        await login(username, password)
      } else {
        const ok = await register(username, password)
        if (ok) setIsLogin(true) // Switch to login after successful registration
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left Hero Section */}
      <div className="hidden lg:flex lg:w-[55%] bg-gradient-hero relative overflow-hidden flex-col justify-between p-12">
        {/* Logo */}
        <div className="flex items-center gap-3 z-10">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <span className="text-xl font-bold text-foreground">Flashcard AI</span>
        </div>

        {/* Hero Content */}
        <div className="z-10 max-w-lg">
          <h1 className="text-4xl md:text-5xl font-bold text-foreground leading-tight mb-4">
            Chào mừng đến với{" "}
            <span className="text-primary">Flashcard AI</span>
            <Sparkles className="inline w-7 h-7 text-yellow-400 ml-2" />
          </h1>
          <p className="text-lg text-muted-foreground leading-relaxed">
            Tạo flashcard thông minh từ tài liệu học tập của bạn
            và học hiệu quả hơn mỗi ngày với AI.
          </p>

          {/* Floating Card Preview */}
          <div className="mt-8 relative">
            <div className="bg-white rounded-2xl shadow-card p-6 max-w-sm border border-border/50">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <span className="text-2xl font-bold text-primary">AI</span>
                </div>
                <div>
                  <p className="font-semibold text-sm text-foreground">Ôn tập thông minh</p>
                </div>
              </div>
              <div className="space-y-3">
                <div className="bg-surface rounded-lg p-3">
                  <p className="text-xs text-muted-foreground font-medium mb-1">Mặt trước</p>
                  <p className="text-sm text-foreground">Quá trình quang hợp diễn ra ở bộ phận nào của lá?</p>
                </div>
                <div className="bg-surface rounded-lg p-3">
                  <p className="text-xs text-muted-foreground font-medium mb-1">Mặt sau</p>
                  <p className="text-sm text-foreground">Quá trình quang hợp diễn ra ở lục lạp trong tế bào mô giậu của lá.</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2.5 py-1 rounded-full bg-green-50 text-green-600 font-medium">Nhận biết</span>
                  <div className="ml-auto">
                    <span className="text-yellow-400 text-sm">★</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Pills */}
        <div className="flex gap-6 z-10">
          {[
            { icon: Upload, title: "Tạo tự động bằng AI", desc: "Trích xuất nội dung và tạo flashcard chính xác, tiết kiệm thời gian." },
            { icon: BarChart3, title: "Ôn tập thông minh", desc: "Hệ thống ôn tập lặp lại ngắt quãng giúp ghi nhớ dài hơn." },
            { icon: Brain, title: "Học mọi lúc, mọi nơi", desc: "Đồng bộ trên mọi thiết bị, học linh hoạt và hiệu quả." },
          ].map((feat, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                <feat.icon className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">{feat.title}</p>
                <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{feat.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Decorative blobs */}
        <div className="absolute -top-20 -right-20 w-80 h-80 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-32 -left-20 w-96 h-96 bg-purple-200/20 rounded-full blur-3xl" />
      </div>

      {/* Right Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 justify-center mb-6">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold">Flashcard AI</span>
          </div>

          {/* Tab Switcher */}
          <div className="flex border-b border-border">
            <button
              onClick={() => setIsLogin(true)}
              className={`flex-1 pb-3 text-sm font-semibold text-center transition-all ${isLogin
                ? "text-primary border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground"
                }`}
            >
              Đăng nhập
            </button>
            <button
              onClick={() => setIsLogin(false)}
              className={`flex-1 pb-3 text-sm font-semibold text-center transition-all ${!isLogin
                ? "text-primary border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground"
                }`}
            >
              Đăng ký
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">Tên tài khoản</label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Nhập tên tài khoản (ít nhất 3 ký tự)"
                  className="w-full h-12 pl-11 pr-4 rounded-xl border border-border bg-white text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all placeholder:text-muted-foreground"
                  autoComplete="username"
                />
                <User className="absolute left-3.5 top-3.5 w-[18px] h-[18px] text-muted-foreground" />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-foreground mb-2 block">Mật khẩu</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nhập mật khẩu"
                  className="w-full h-12 pl-11 pr-11 rounded-xl border border-border bg-white text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all placeholder:text-muted-foreground"
                  autoComplete="current-password"
                />
                <Lock className="absolute left-3.5 top-3.5 w-[18px] h-[18px] text-muted-foreground" />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-3.5 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="w-[18px] h-[18px]" /> : <Eye className="w-[18px] h-[18px]" />}
                </button>
              </div>
            </div>

            {!isLogin && (
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">Xác nhận mật khẩu</label>
                <div className="relative">
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Nhập lại mật khẩu"
                    className="w-full h-12 pl-11 pr-4 rounded-xl border border-border bg-white text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all placeholder:text-muted-foreground"
                    autoComplete="new-password"
                  />
                  <Lock className="absolute left-3.5 top-3.5 w-[18px] h-[18px] text-muted-foreground" />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-xl bg-primary text-white font-semibold text-sm hover:bg-primary/90 active:bg-primary/80 transition-all flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <ArrowRight className="w-4 h-4" />
                  {isLogin ? "Đăng nhập" : "Tạo tài khoản"}
                </>
              )}
            </button>
          </form>



          {/* Switch text */}
          <p className="text-center text-sm text-muted-foreground">
            {isLogin ? "Chưa có tài khoản? " : "Đã có tài khoản? "}
            <button
              onClick={() => setIsLogin(!isLogin)}
              className="text-primary font-semibold hover:underline"
            >
              {isLogin ? "Đăng ký" : "Đăng nhập"}
            </button>
          </p>

          {/* Footer */}
          <div className="flex items-center justify-center gap-4 text-xs text-muted-foreground pt-4">
            <span className="flex items-center gap-1">
              <Lock className="w-3 h-3" />
              Bảo mật dữ liệu tuyệt đối
            </span>
            <span>•</span>
            <span>Không chia sẻ thông tin với bên thứ ba</span>
          </div>
        </div>
      </div>
    </div>
  )
}
