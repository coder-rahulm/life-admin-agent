import React, { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Mail, TrendingUp, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react'
import TaskCard from '../components/TaskCard'
import AgentPanel from '../components/AgentPanel'
import ApprovalGate from '../components/ApprovalGate'
import { useAgentStream } from '../hooks/useAgentStream'

const API = 'http://localhost:8000'

function StatCard({ icon, label, value, sub, color = 'blue' }) {
    const colors = {
        blue: 'text-blue-400',
        red: 'text-red-400',
        amber: 'text-amber-400',
        green: 'text-emerald-400',
    }
    return (
        <div className="stat-card">
            <div className={`text-2xl ${colors[color]}`}>{icon}</div>
            <div>
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="text-xs text-white/50">{label}</p>
                {sub && <p className="text-xs text-white/30 mt-0.5">{sub}</p>}
            </div>
        </div>
    )
}

export default function Dashboard() {
    const [tasks, setTasks] = useState([])
    const [insights, setInsights] = useState(null)
    const [loadingTasks, setLoadingTasks] = useState(false)
    const [processingEmails, setProcessingEmails] = useState(false)
    const [filter, setFilter] = useState('all')

    const {
        events, isRunning, connect, disconnect, pendingApprovals: streamApprovals,
        setPendingApprovals, clearEvents,
    } = useAgentStream()

    const [localApprovals, setLocalApprovals] = useState([])
    const allApprovals = [...localApprovals, ...streamApprovals].filter(
        (a, i, arr) => arr.findIndex(b => b.id === a.id) === i
    )

    const fetchTasks = useCallback(async () => {
        setLoadingTasks(true)
        try {
            const res = await fetch(`${API}/api/tasks`)
            const data = await res.json()
            setTasks(data.tasks || [])
        } catch (e) {
            console.error(e)
        } finally {
            setLoadingTasks(false)
        }
    }, [])

    const fetchInsights = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/insights`)
            setInsights(await res.json())
        } catch (e) { }
    }, [])

    const fetchPendingApprovals = useCallback(async () => {
        try {
            const res = await fetch(`${API}/api/pending-approvals`)
            const data = await res.json()
            setLocalApprovals(data.approvals || [])
        } catch (e) { }
    }, [])

    useEffect(() => {
        fetchTasks()
        fetchInsights()
        fetchPendingApprovals()
    }, [])

    const handleProcessEmails = async () => {
        setProcessingEmails(true)
        clearEvents()
        connect(false)    // connect SSE first
        try {
            await fetch(`${API}/api/process-emails`, { method: 'POST' })
            setTimeout(() => {
                fetchTasks()
                fetchInsights()
                fetchPendingApprovals()
                setProcessingEmails(false)
            }, 2000)
        } catch (e) {
            setProcessingEmails(false)
        }
    }

    const handleStartDemo = () => {
        clearEvents()
        connect(true)   // demo SSE stream
        setTimeout(() => {
            fetchTasks()
            fetchInsights()
            fetchPendingApprovals()
        }, 8000)
    }

    const handleStatusUpdate = async (taskId, status) => {
        await fetch(`${API}/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status }),
        })
        fetchTasks()
        fetchInsights()
    }

    const handleApprove = async (approvalId) => {
        await fetch(`${API}/api/approve-action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approval_id: approvalId, approved: true }),
        })
        fetchPendingApprovals()
    }

    const handleReject = async (approvalId, reason) => {
        await fetch(`${API}/api/approve-action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approval_id: approvalId, approved: false, reason }),
        })
        fetchPendingApprovals()
    }

    const filteredTasks = tasks.filter(t => {
        if (filter === 'all') return true
        if (filter === 'pending') return t.status === 'pending'
        if (filter === 'p1') return t.priority === 'P1'
        if (filter === 'p2') return t.priority === 'P2'
        if (filter === 'p3') return t.priority === 'P3'
        return true
    })

    return (
        <div className="space-y-6">
            {/* Stats Bar */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard icon="📋" label="Total Tasks" value={insights?.total_tasks || tasks.length} color="blue" />
                <StatCard
                    icon="🚨"
                    label="P1 Alerts"
                    value={insights?.p1_count || tasks.filter(t => t.priority === 'P1').length}
                    color="red"
                />
                <StatCard
                    icon="💸"
                    label="Monthly Spend"
                    value={`₹${(insights?.monthly_spend || 0).toLocaleString('en-IN')}`}
                    color="amber"
                />
                <StatCard
                    icon="📦"
                    label="Unused Subs"
                    value={insights?.unused_subscriptions || 0}
                    sub={`₹${(insights?.unused_spend || 0).toLocaleString('en-IN')} wasted`}
                    color="green"
                />
            </div>

            {/* Agent Panel */}
            <AgentPanel
                events={events}
                isRunning={isRunning}
                isConnected={true}
                onStartDemo={handleStartDemo}
                onStop={disconnect}
            />

            {/* Pending Approvals */}
            {allApprovals.length > 0 && (
                <div className="space-y-3">
                    <h2 className="text-white font-semibold flex items-center gap-2">
                        <AlertCircle size={16} className="text-amber-400" />
                        Pending Approvals ({allApprovals.length})
                    </h2>
                    {allApprovals.map(approval => (
                        <ApprovalGate
                            key={approval.id}
                            approval={approval}
                            onApprove={handleApprove}
                            onReject={handleReject}
                        />
                    ))}
                </div>
            )}

            {/* Actions Row */}
            <div className="flex items-center justify-between">
                <div className="flex gap-2 flex-wrap">
                    {['all', 'pending', 'p1', 'p2', 'p3'].map(f => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${filter === f
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white'
                                }`}
                        >
                            {f.toUpperCase()}
                        </button>
                    ))}
                </div>
                <div className="flex gap-2">
                    <button onClick={fetchTasks} className="btn-secondary text-sm">
                        <RefreshCw size={14} />
                        Refresh
                    </button>
                    <button
                        onClick={handleProcessEmails}
                        disabled={processingEmails}
                        className="btn-primary text-sm"
                    >
                        {processingEmails
                            ? <Loader2 size={14} className="animate-spin" />
                            : <Mail size={14} />}
                        Process Emails
                    </button>
                </div>
            </div>

            {/* Task List */}
            <div>
                {loadingTasks ? (
                    <div className="flex justify-center py-12">
                        <Loader2 size={32} className="animate-spin text-blue-400" />
                    </div>
                ) : filteredTasks.length === 0 ? (
                    <div className="glass-card p-10 text-center">
                        <CheckCircle2 size={48} className="text-emerald-400/30 mx-auto mb-3" />
                        <p className="text-white/40">No tasks found. Click "Process Emails" or "▶ Demo" to get started!</p>
                    </div>
                ) : (
                    <div className="grid gap-3">
                        {filteredTasks.map(task => (
                            <TaskCard key={task.id} task={task} onStatusUpdate={handleStatusUpdate} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
