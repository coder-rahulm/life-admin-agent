import React from 'react'
import { AlertCircle, Calendar, DollarSign, CheckCircle2, Clock, ChevronDown, ChevronUp } from 'lucide-react'

const CATEGORY_ICONS = {
    bill: '🧾',
    deadline: '⏰',
    subscription: '📦',
    renewal: '🔄',
    reminder: '🔔',
}

const PRIORITY_STYLES = {
    P1: {
        badge: 'badge-p1',
        border: 'border-red-500/30',
        glow: 'hover:shadow-red-500/10',
        bg: 'bg-red-500/5',
    },
    P2: {
        badge: 'badge-p2',
        border: 'border-amber-500/30',
        glow: 'hover:shadow-amber-500/10',
        bg: 'bg-amber-500/5',
    },
    P3: {
        badge: 'badge-p3',
        border: 'border-blue-500/30',
        glow: 'hover:shadow-blue-500/10',
        bg: 'bg-blue-500/5',
    },
}

export default function TaskCard({ task, onStatusUpdate }) {
    const [expanded, setExpanded] = React.useState(false)
    const [loading, setLoading] = React.useState(false)

    const styles = PRIORITY_STYLES[task.priority] || PRIORITY_STYLES.P3
    const icon = CATEGORY_ICONS[task.category] || '📌'

    const isOverdue = task.due_date && new Date(task.due_date) < new Date()
    const daysLeft = task.due_date
        ? Math.ceil((new Date(task.due_date) - new Date()) / (1000 * 60 * 60 * 24))
        : null

    const handleStatus = async (status) => {
        setLoading(true)
        try {
            await onStatusUpdate(task.id, status)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div
            className={`glass-card border ${styles.border} ${styles.bg} hover:shadow-lg ${styles.glow} transition-all duration-200 animate-fade-in`}
        >
            <div className="p-4">
                <div className="flex items-start gap-3">
                    {/* Icon */}
                    <span className="text-xl mt-0.5">{icon}</span>

                    {/* Main content */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className={styles.badge}>{task.priority}</span>
                            <span className="text-xs text-white/40 capitalize bg-white/5 px-2 py-0.5 rounded-full">
                                {task.category}
                            </span>
                            {task.status === 'done' && (
                                <span className="text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">✓ Done</span>
                            )}
                            {task.status === 'snoozed' && (
                                <span className="text-xs text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full">⏰ Snoozed</span>
                            )}
                        </div>

                        <h3 className="text-white font-medium text-sm leading-tight mb-2">{task.title}</h3>

                        <div className="flex items-center gap-4 text-xs text-white/50">
                            {task.due_date && (
                                <span className={`flex items-center gap-1 ${isOverdue ? 'text-red-400' : daysLeft <= 3 ? 'text-amber-400' : 'text-white/50'}`}>
                                    <Calendar size={12} />
                                    {isOverdue ? `Overdue by ${-daysLeft}d` : daysLeft === 0 ? 'Due today' : `${daysLeft}d left`}
                                </span>
                            )}
                            {task.amount > 0 && (
                                <span className="flex items-center gap-1 text-emerald-400/80">
                                    <DollarSign size={12} />
                                    ₹{task.amount.toLocaleString('en-IN')}
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Actions */}
                    {task.status === 'pending' && (
                        <div className="flex gap-1 ml-2 shrink-0">
                            <button
                                onClick={() => handleStatus('done')}
                                disabled={loading}
                                className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-colors"
                                title="Mark done"
                            >
                                <CheckCircle2 size={14} />
                            </button>
                            <button
                                onClick={() => handleStatus('snoozed')}
                                disabled={loading}
                                className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 transition-colors"
                                title="Snooze"
                            >
                                <Clock size={14} />
                            </button>
                        </div>
                    )}

                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-1 text-white/30 hover:text-white/60 transition-colors shrink-0"
                    >
                        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                </div>

                {/* Explanation tooltip */}
                {expanded && task.explanation && (
                    <div className="mt-3 pt-3 border-t border-white/5 animate-slide-up">
                        <div className="flex items-start gap-2">
                            <AlertCircle size={13} className="text-blue-400 mt-0.5 shrink-0" />
                            <p className="text-xs text-blue-300/80 leading-relaxed">{task.explanation}</p>
                        </div>
                        {task.source_email_subject && (
                            <p className="text-xs text-white/30 mt-2">📧 {task.source_email_subject}</p>
                        )}
                        {task.confidence && (
                            <p className="text-xs text-white/30 mt-1">
                                Agent confidence: <span className="text-emerald-400">{(task.confidence * 100).toFixed(0)}%</span>
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}
