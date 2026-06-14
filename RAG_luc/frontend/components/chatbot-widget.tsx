"use client"

import * as React from "react"
import { MessageCircle, X, Send, Loader2, Bot, User, Sparkles, Minimize2 } from "lucide-react"

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

export function ChatbotWidget() {
  const [isOpen, setIsOpen] = React.useState(false)
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Xin chào! 👋 Tôi là trợ lý AI của Flashcard AI. Tôi có thể giúp bạn:\n\n• Giải đáp về nội dung tài liệu\n• Hướng dẫn sử dụng ứng dụng\n• Mẹo học tập hiệu quả\n\nBạn cần hỗ trợ gì?",
    },
  ])
  const [input, setInput] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const scrollRef = React.useRef<HTMLDivElement>(null)
  const inputRef = React.useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom when new messages arrive
  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  // Focus input when chat opens
  React.useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 200)
    }
  }, [isOpen])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMsg = input.trim()
    setInput("")
    const newMessages: ChatMessage[] = [...messages, { role: "user", content: userMsg }]
    setMessages(newMessages)
    setIsLoading(true)

    try {
      const res = await fetch("/api/general/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg,
          history: messages.slice(1).map((m) => ({ role: m.role, content: m.content })),
        }),
      })

      const data = await res.json()

      if (!res.ok) {
        setMessages([
          ...newMessages,
          { role: "assistant", content: data.error || "Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại." },
        ])
      } else {
        setMessages([...newMessages, { role: "assistant", content: data.response }])
      }
    } catch {
      setMessages([
        ...newMessages,
        { role: "assistant", content: "Không thể kết nối với server. Vui lòng kiểm tra kết nối mạng." },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {/* ── Floating Action Button ─────────────────────────────── */}
      <button
        id="chatbot-fab"
        onClick={() => setIsOpen(!isOpen)}
        className={`
          fixed bottom-6 right-6 z-50
          w-14 h-14 rounded-full
          flex items-center justify-center
          shadow-lg hover:shadow-xl
          transition-all duration-300 ease-out
          ${isOpen
            ? "bg-zinc-700 hover:bg-zinc-800 scale-90 rotate-90"
            : "bg-[var(--fc-primary)] hover:bg-[var(--fc-primary-dark)] scale-100 rotate-0"
          }
        `}
        style={{ 
          boxShadow: isOpen 
            ? "0 4px 14px rgba(0,0,0,0.15)" 
            : "0 4px 20px rgba(67, 97, 238, 0.4)" 
        }}
        aria-label={isOpen ? "Đóng chat" : "Mở trợ lý AI"}
      >
        {isOpen ? (
          <X className="w-6 h-6 text-white" />
        ) : (
          <MessageCircle className="w-6 h-6 text-white" />
        )}
      </button>

      {/* ── Unread indicator dot ─────────────────────────────── */}
      {!isOpen && messages.length <= 1 && (
        <span className="fixed bottom-[4.25rem] right-[1.25rem] z-50 w-3 h-3 bg-red-500 rounded-full animate-pulse pointer-events-none" />
      )}

      {/* ── Chat Panel ─────────────────────────────────────────── */}
      <div
        className={`
          fixed bottom-24 right-6 z-50
          w-[380px] max-w-[calc(100vw-2rem)]
          flex flex-col
          rounded-2xl overflow-hidden
          border border-zinc-200/80
          bg-white
          transition-all duration-300 ease-out origin-bottom-right
          ${isOpen
            ? "opacity-100 scale-100 translate-y-0 pointer-events-auto"
            : "opacity-0 scale-95 translate-y-4 pointer-events-none"
          }
        `}
        style={{
          height: "min(520px, calc(100vh - 8rem))",
          boxShadow: "0 8px 40px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-gradient-to-r from-[var(--fc-primary)] to-[#5b72f5] text-white shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold leading-tight">Trợ lý AI</h3>
              <p className="text-[11px] text-white/70">Flashcard AI Assistant</p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
            aria-label="Thu nhỏ"
          >
            <Minimize2 className="w-4 h-4" />
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4" style={{ scrollBehavior: "smooth" }}>
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
              {/* Avatar */}
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                  msg.role === "assistant"
                    ? "bg-[var(--fc-primary-light)] text-[var(--fc-primary)]"
                    : "bg-zinc-100 text-zinc-500"
                }`}
              >
                {msg.role === "assistant" ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
              </div>

              {/* Bubble */}
              <div
                className={`max-w-[80%] px-3.5 py-2.5 text-[13px] leading-relaxed rounded-2xl ${
                  msg.role === "assistant"
                    ? "bg-zinc-50 text-zinc-800 rounded-tl-md"
                    : "bg-[var(--fc-primary)] text-white rounded-tr-md"
                }`}
                style={{
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {isLoading && (
            <div className="flex gap-2.5">
              <div className="w-7 h-7 rounded-full bg-[var(--fc-primary-light)] text-[var(--fc-primary)] flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-zinc-50 px-4 py-3 rounded-2xl rounded-tl-md">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-zinc-300 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-zinc-300 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-zinc-300 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="shrink-0 border-t border-zinc-100 px-3 py-3 bg-white">
          <div className="flex items-center gap-2 bg-zinc-50 rounded-xl px-3 py-1.5 border border-zinc-200/60 focus-within:border-[var(--fc-primary)]/40 focus-within:ring-2 focus-within:ring-[var(--fc-primary)]/10 transition-all">
            <input
              ref={inputRef}
              id="chatbot-input"
              type="text"
              placeholder="Nhập câu hỏi..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              className="flex-1 bg-transparent text-[13px] text-zinc-800 placeholder:text-zinc-400 outline-none py-1.5 disabled:opacity-50"
            />
            <button
              id="chatbot-send"
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all shrink-0 ${
                input.trim() && !isLoading
                  ? "bg-[var(--fc-primary)] text-white hover:bg-[var(--fc-primary-dark)] shadow-sm"
                  : "bg-zinc-200/60 text-zinc-400 cursor-not-allowed"
              }`}
              aria-label="Gửi"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-center text-[10px] text-zinc-400 mt-2">
            Powered by Flashcard AI • GPT-4o-mini
          </p>
        </div>
      </div>
    </>
  )
}
