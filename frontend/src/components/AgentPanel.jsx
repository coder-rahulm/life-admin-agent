import React, { useRef, useEffect } from 'react'
import { ChevronRight, Loader2, Brain, Zap, Eye, CheckCircle } from 'lucide-react'

const EVENT_STYLES = {
    thought: { icon: <Brain size={13} />, label: 'Thought', cls: 'agent-thought', border: 'border-blue-500/30', bg: 'bg-blue-500/5' },
    action: { icon: <Zap size={13} />, label: 'Action', cls: 'agent-action', border: 'border-purple-500/30', bg: 'bg-purple-500/5' },
    observation: { icon: <Eye size={13} />, label: 'Observation', cls: 'agent-observation', border: 'border-emerald-500/30', bg: 'bg-emerald-500/5' },
    confidence: { icon: <CheckCircle size={13} />, label: 'Confidence', cls: 'agent-confidence', border: 'border-amber-500/30', bg: 'bg-amber-500/5' },
    retry: { icon: '🔄', label: 'Retry', cls: 'text-orange-300 text-sm', border: 'border-orange-500/30', bg: 'bg-orange-500/5' },
    final_answer: { icon: '🎯', label: 'Final Answer', cls: 'agent-final', border: 'border-white/20', bg: 'bg-white/5' },
    email_start: { icon: '📧', label: 'Processing Email', cls: 'text-white/60 text-sm', border: 'border-white/10', bg: 'bg-white/3' },
    email_done: { icon: '✅', label: 'Email Done', cls: 'text-emerald-400 text-sm', border: 'border-emerald-500/20', bg: 'bg-emerald-500/5' },
    pending_approval: { icon: '🔒', label: 'Approval Required', cls: 'text-amber-300 text-sm', border: 'border-amber-500/30', bg: 'bg-amber-500/5' },
    error: { icon: '❌', label: 'Error', cls: 'text-red-400 text-sm', border: 'border-red-500/30', bg: 'bg-red-500/5' },
}

function EventBubble({ event }) {
    const style = EVENT_STYLES[event.type] || EVENT_STYLES.thought

    const renderContent = () => {
        if (event.type === 'thought') return event.content
        if (event.type === 'action') return (
            <span>
                <span className="text-purple-200 font-semibold">{event.tool}</span>
                <span className="text-white/40">(</span>
                <span className="text-purple-300/70">{JSON.stringify(event.args || {})}</span>
                <span className="text-white/40">)</span>
            </span>
        )
        if (event.type === 'observation') {
            const content = event.content
            if (typeof content === 'object') {
                return <span className="font-mono text-xs">{JSON.stringify(content).slice(0, 200)}{JSON.stringify(content).length > 200 ? '...' : ''}</span>
            }
            return String(content)
        }
        if (event.type === 'confidence') return (
            <span>
                Score: <span className={event.score >= 0.7 ? 'text-emerald-400' : 'text-red-400'}>{(event.score * 100).toFixed(0)}%</span>
                {event.retry > 0 && <span className="text-orange-400 ml-2">Retry {event.retry}</span>}
            </span>
        )
        if (event.type === 'retry') return `Retrying (attempt ${event.attempt}) — ${event.reason}`
        if (event.type === 'final_answer') {
            const c = event.content || {}
            return `Extracted ${c.task_count || 0} task(s) • ${c.p1_count || 0} P1`
        }
        if (event.type === 'email_start') return `📧 Starting: ${event.subject || event.email_subject || ''}`
        if (event.type === 'email_done') return `Finished email ${(event.email_index ?? 0) + 1}`
        if (event.type === 'pending_approval') {
            const c = event.content || {}
            return `${c.action_type || 'action'} for "${c.task_title || ''}"`
        }
        if (event.type === 'error') return event.content
        return JSON.stringify(event.content || '').slice(0, 100)
    }

    return (
        <div className={`border ${style.border} ${style.bg} rounded-lg p-2.5 mb-2 animate-fade-in`}>
            <div className="flex items-center gap-1.5 mb-1">
                <span className={`${style.cls} flex items-center`}>{style.icon}</span>
                <span className="text-white/30 text-xs uppercase tracking-wider">{style.label}</span>
            </div>
            <p className={`${style.cls} break-words`}>{renderContent()}</p>
        </div>
    )
}

export default function AgentPanel({ events, isConnected, isRunning, onStartDemo, onStop }) {
    const [collapsed, setCollapsed] = React.useState(false)
    const bottomRef = useRef(null)

    useEffect(() => {
        if (!collapsed) {
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
        }
    }, [events, collapsed])

    return (
        <div className={`glass-card border border-blue-500/20 transition-all duration-300 ${collapsed ? 'h-12' : 'h-[500px]'} flex flex-col overflow-hidden`}>
            {/* Header */}
            <div className="flex items-center justify-between p-3 border-b border-white/5 shrink-0">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isConnected || isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-white/20'}`} />
                    <span className="text-sm font-semibold text-white">Agent Panel</span>
                    {isRunning && (
                        <span className="flex items-center gap-1 text-xs text-blue-300">
                            <Loader2 size={11} className="animate-spin" />
                            Running
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {!isRunning && (
                        <button onClick={onStartDemo} className="text-xs px-2 py-1 bg-blue-600/60 hover:bg-blue-500 rounded text-white transition-colors">
                            ▶ Demo
                        </button>
                    )}
                    {isRunning && (
                        <button onClick={onStop} className="text-xs px-2 py-1 bg-red-600/60 hover:bg-red-500 rounded text-white transition-colors">
                            ■ Stop
                        </button>
                    )}
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="text-white/40 hover:text-white transition-colors"
                    >
                        <ChevronRight size={15} className={`transition-transform ${collapsed ? '' : 'rotate-90'}`} />
                    </button>
                </div>
            </div>

            {/* Events stream */}
            {!collapsed && (
                <div className="flex-1 overflow-y-auto p-3 space-y-1">
                    {events.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center">
                            <Brain size={32} className="text-blue-400/30 mb-3" />
                            <p className="text-white/30 text-sm">Agent scratchpad will appear here.</p>
                            <p className="text-white/20 text-xs mt-1">Click ▶ Demo to see it live!</p>
                        </div>
                    ) : (
                        events.map((evt, i) => (
                            <EventBubble key={i} event={evt} />
                        ))
                    )}
                    <div ref={bottomRef} />
                </div>
            )}
        </div>
    )
}
