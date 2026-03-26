import React, { useState } from 'react'
import { AlertTriangle, CheckCircle, XCircle, Loader2 } from 'lucide-react'

const ACTION_LABELS = {
    send_notification: {
        icon: '🔔',
        title: 'Send Notification',
        description: (p) => `Send a P1 alert for "${p.task_title || 'task'}"`,
        color: 'blue',
    },
    cancel_subscription: {
        icon: '🚫',
        title: 'Cancel Subscription',
        description: (p) => `Cancel subscription for "${p.task_title || p.service_name || 'service'}"`,
        color: 'red',
    },
    mark_paid: {
        icon: '💳',
        title: 'Mark as Paid',
        description: (p) => `Mark bill of ₹${p.amount?.toLocaleString('en-IN') || '0'} as paid`,
        color: 'green',
    },
}

const COLOR_MAP = {
    blue: {
        border: 'border-blue-500/40',
        icon_bg: 'bg-blue-500/10',
        icon_color: 'text-blue-400',
        approve_btn: 'bg-blue-600 hover:bg-blue-500',
    },
    red: {
        border: 'border-red-500/40',
        icon_bg: 'bg-red-500/10',
        icon_color: 'text-red-400',
        approve_btn: 'bg-red-600 hover:bg-red-500',
    },
    green: {
        border: 'border-emerald-500/40',
        icon_bg: 'bg-emerald-500/10',
        icon_color: 'text-emerald-400',
        approve_btn: 'bg-emerald-600 hover:bg-emerald-500',
    },
}

export default function ApprovalGate({ approval, onApprove, onReject }) {
    const [loading, setLoading] = useState(false)
    const [rejecting, setRejecting] = useState(false)
    const [reason, setReason] = useState('')
    const [done, setDone] = useState(false)
    const [result, setResult] = useState(null)

    const meta = ACTION_LABELS[approval.action_type] || {
        icon: '⚙️',
        title: 'Agent Action',
        description: () => 'Agent wants to perform an action',
        color: 'blue',
    }
    const colors = COLOR_MAP[meta.color] || COLOR_MAP.blue
    const payload = approval.payload || approval

    const handleApprove = async () => {
        setLoading(true)
        try {
            await onApprove(approval.id)
            setResult('approved')
            setDone(true)
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    const handleConfirmReject = async () => {
        if (!reason.trim()) return
        setLoading(true)
        try {
            await onReject(approval.id, reason)
            setResult('rejected')
            setDone(true)
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    if (done) {
        return (
            <div className={`glass-card border ${colors.border} p-4 animate-fade-in opacity-60`}>
                <div className="flex items-center gap-2">
                    {result === 'approved'
                        ? <CheckCircle size={16} className="text-emerald-400" />
                        : <XCircle size={16} className="text-red-400" />}
                    <span className="text-sm text-white/60">
                        {result === 'approved' ? 'Approved' : 'Rejected'}: {meta.title}
                    </span>
                </div>
            </div>
        )
    }

    return (
        <div className={`glass-card border ${colors.border} p-4 animate-slide-up`}>
            <div className="flex items-start gap-3">
                <div className={`${colors.icon_bg} ${colors.icon_color} p-2 rounded-lg shrink-0`}>
                    <AlertTriangle size={16} />
                </div>
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">{meta.icon}</span>
                        <span className="text-white font-semibold text-sm">{meta.title}</span>
                        <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full border border-amber-500/30">
                            Approval Required
                        </span>
                    </div>
                    <p className="text-white/60 text-sm mb-1">{meta.description(payload)}</p>
                    {payload.explanation && (
                        <p className="text-xs text-white/40 italic mb-3">{payload.explanation}</p>
                    )}

                    {rejecting ? (
                        <div className="mt-2 space-y-2">
                            <input
                                type="text"
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                placeholder="Why are you rejecting this? (1 sentence)"
                                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-white/30 focus:outline-none focus:border-white/30"
                            />
                            <div className="flex gap-2">
                                <button
                                    onClick={handleConfirmReject}
                                    disabled={!reason.trim() || loading}
                                    className="btn-danger text-xs py-1.5"
                                >
                                    {loading ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />}
                                    Confirm Reject
                                </button>
                                <button onClick={() => setRejecting(false)} className="btn-secondary text-xs py-1.5">
                                    Cancel
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="flex gap-2 mt-3">
                            <button
                                onClick={handleApprove}
                                disabled={loading}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-colors ${colors.approve_btn}`}
                            >
                                {loading ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle size={13} />}
                                Approve
                            </button>
                            <button
                                onClick={() => setRejecting(true)}
                                disabled={loading}
                                className="btn-secondary text-xs py-1.5"
                            >
                                <XCircle size={13} />
                                Reject
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
