import React, { useState, useRef, useEffect, Component } from 'react'
import { MessageCircle, X, Send, Loader2, Bot, User, PackagePlus, ChevronDown } from 'lucide-react'

// Relative URL — Vite proxy forwards /api to localhost:8000
const API = ''

const QUICK_ACTIONS = [
    { label: '📋 What can you do?', text: 'What can this app do? Give me a quick tour.' },
    { label: '➕ Add subscription', text: 'I want to add a subscription manually.' },
    { label: '🎯 How does demo work?', text: 'How do I run the demo mode?' },
    { label: '📊 Explain priorities', text: 'How does the agent decide P1/P2/P3 priorities?' },
]

// ── Error boundary so a crash inside chat NEVER blanks the whole page ──────────
class ChatErrorBoundary extends Component {
    constructor(props) { super(props); this.state = { hasError: false } }
    static getDerivedStateFromError() { return { hasError: true } }
    render() {
        if (this.state.hasError)
            return (
                <div className="fixed bottom-24 right-6 z-50 p-4 bg-red-900/80 border border-red-500/30 rounded-xl text-xs text-red-300 max-w-xs">
                    ⚠️ Chatbot crashed — please refresh the page.
                </div>
            )
        return this.props.children
    }
}

// ── Individual message bubble ─────────────────────────────────────────────────
function MessageBubble({ msg }) {
    const isUser = msg.role === 'user'
    const isSystem = msg.role === 'system'
    // Guard: content may be undefined/null if something went wrong
    const raw = (msg.content ?? '').replace(/```json[\s\S]*?```/g, '').trim()

    if (isSystem) {
        return (
            <div className="flex justify-center mb-3">
                <span className="text-xs text-white/30 bg-white/5 px-3 py-1 rounded-full">{raw}</span>
            </div>
        )
    }

    return (
        <div className={`flex gap-2 mb-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${isUser ? 'bg-blue-600' : 'bg-gradient-to-br from-purple-600 to-blue-600'
                }`}>
                {isUser ? <User size={13} /> : <Bot size={13} />}
            </div>

            <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${isUser
                    ? 'bg-blue-600 text-white rounded-tr-sm'
                    : 'bg-white/8 border border-white/10 text-white/90 rounded-tl-sm'
                }`}>
                {raw || <span className="opacity-40 italic">...</span>}

                {msg.action?.type === 'subscription_added' && (
                    <div className="mt-2 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2">
                        <PackagePlus size={12} className="text-emerald-400" />
                        <span className="text-xs text-emerald-400">
                            ✅ Added <strong>{msg.action.service_name}</strong> — ₹{msg.action.amount}/{msg.action.billing_cycle}
                        </span>
                    </div>
                )}
            </div>
        </div>
    )
}

// ── Main chatbot component ────────────────────────────────────────────────────
function ChatBotInner() {
    const [open, setOpen] = useState(false)
    const [messages, setMessages] = useState([
        {
            role: 'assistant',
            content: "👋 Hi! I'm your Life Admin Assistant powered by Groq (LLaMA 3.3 70B).\n\nI can help you:\n• Navigate the app\n• Add subscriptions manually\n• Explain how the AI agent works\n• Answer questions about your tasks & finances\n\nWhat would you like to do?",
        },
    ])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [unread, setUnread] = useState(0)
    const [chatReady, setChatReady] = useState(null) // null=unknown, true=ready, false=not configured
    const bottomRef = useRef(null)
    const inputRef = useRef(null)

    useEffect(() => {
        if (open) {
            setUnread(0)
            setTimeout(() => inputRef.current?.focus(), 100)
            // Check if GROQ_API_KEY is configured
            if (chatReady === null) {
                fetch(`${API}/api/chat/status`)
                    .then(r => r.json())
                    .then(d => setChatReady(d.ready))
                    .catch(() => setChatReady(false))
            }
        }
    }, [open])

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
        if (!open && messages[messages.length - 1]?.role === 'assistant') {
            setUnread(n => n + 1)
        }
    }, [messages])

    const sendMessage = async (text) => {
        if (!text.trim() || loading) return
        const userMsg = { role: 'user', content: text }
        setMessages(prev => [...prev, userMsg])
        setInput('')
        setLoading(true)

        const history = [...messages, userMsg]
            .filter(m => m.role !== 'system')
            .map(m => ({ role: m.role, content: m.content }))

        try {
            const res = await fetch(`${API}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: history }),
            })
            if (!res.ok) throw new Error(`Server error ${res.status} — is the backend running?`)
            const data = await res.json()
            const reply = (typeof data.reply === 'string' && data.reply)
                ? data.reply
                : '⚠️ Empty response from server.'
            setMessages(prev => [...prev, { role: 'assistant', content: reply, action: data.action ?? null }])

            if (data.action?.type === 'subscription_added') {
                setMessages(prev => [
                    ...prev,
                    { role: 'system', content: `"${data.action.service_name}" added ✓ — check Subscriptions page` },
                ])
            }
        } catch (err) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `❌ ${err.message || 'Connection failed'}.\n\nMake sure the backend is running:\ncd backend && uvicorn main:app --reload --port 8000`,
            }])
        } finally {
            setLoading(false)
        }
    }

    const handleKey = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            e.stopPropagation()
            sendMessage(input)
        }
    }

    return (
        <>
            {/* ── Floating bubble ── */}
            <button
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(o => !o) }}
                className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 shadow-2xl flex items-center justify-center transition-all duration-200 hover:scale-110"
                title="Open AI Assistant"
            >
                {open ? <X size={22} /> : <MessageCircle size={22} />}
                {!open && unread > 0 && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs flex items-center justify-center font-bold">
                        {unread}
                    </span>
                )}
            </button>

            {/* ── Chat window ── */}
            {open && (
                <div
                    className="fixed bottom-24 right-6 z-50 w-80 sm:w-96 h-[520px] flex flex-col glass-card border border-purple-500/30 shadow-2xl overflow-hidden"
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5 bg-gradient-to-r from-purple-600/20 to-blue-600/20 shrink-0">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center">
                            <Bot size={16} />
                        </div>
                        <div>
                            <p className="text-white text-sm font-semibold">Life Admin Assistant</p>
                            <p className="text-white/40 text-xs">Powered by Groq · LLaMA 3.3 70B</p>
                        </div>
                        <button
                            type="button"
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(false) }}
                            className="ml-auto text-white/30 hover:text-white transition-colors"
                        >
                            <ChevronDown size={16} />
                        </button>
                    </div>

                    {/* GROQ key warning banner */}
                    {chatReady === false && (
                        <div className="mx-3 mt-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl shrink-0">
                            <p className="text-xs text-amber-400 font-semibold mb-1">⚠️ Chatbot not configured</p>
                            <p className="text-xs text-amber-300/80">
                                Add your <code className="bg-white/10 px-1 rounded">GROQ_API_KEY</code> to{' '}
                                <code className="bg-white/10 px-1 rounded">backend/.env</code>.{' '}
                                Get a free key at{' '}
                                <a href="https://console.groq.com" target="_blank" rel="noreferrer" className="underline">
                                    console.groq.com
                                </a>
                            </p>
                        </div>
                    )}

                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-4">
                        {messages.map((msg, i) => (
                            <MessageBubble key={i} msg={msg} />
                        ))}
                        {loading && (
                            <div className="flex gap-2 mb-3">
                                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center">
                                    <Bot size={13} />
                                </div>
                                <div className="bg-white/8 border border-white/10 rounded-2xl rounded-tl-sm px-3 py-2.5">
                                    <div className="flex gap-1 items-center">
                                        <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {/* Quick actions (only on first open) */}
                    {messages.length <= 1 && (
                        <div className="px-4 pb-2 flex flex-wrap gap-1.5 shrink-0">
                            {QUICK_ACTIONS.map(action => (
                                <button
                                    type="button"
                                    key={action.text}
                                    onClick={(e) => { e.preventDefault(); sendMessage(action.text) }}
                                    className="text-xs px-2.5 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-white/70 hover:text-white transition-colors"
                                >
                                    {action.label}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input row */}
                    <div className="px-3 py-3 border-t border-white/5 flex gap-2 items-end shrink-0">
                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKey}
                            placeholder="Say 'hi' or 'add Spotify ₹119/month'…"
                            rows={1}
                            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50 transition-colors max-h-24"
                            style={{ minHeight: '38px' }}
                        />
                        <button
                            type="button"
                            onClick={(e) => { e.preventDefault(); sendMessage(input) }}
                            disabled={!input.trim() || loading}
                            className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 flex items-center justify-center shrink-0 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                        </button>
                    </div>
                </div>
            )}
        </>
    )
}

export default function ChatBot() {
    return (
        <ChatErrorBoundary>
            <ChatBotInner />
        </ChatErrorBoundary>
    )
}
