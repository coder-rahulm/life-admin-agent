import React, { useState, useEffect } from 'react'
import { Loader2, RefreshCw, AlertTriangle } from 'lucide-react'

const API = 'http://localhost:8000'

function CancelScoreBar({ score, maxScore }) {
    const pct = maxScore > 0 ? Math.min((score / maxScore) * 100, 100) : 0
    return (
        <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${pct > 70 ? 'bg-red-500' : pct > 40 ? 'bg-amber-500' : 'bg-blue-500'
                        }`}
                    style={{ width: `${pct}%` }}
                />
            </div>
            <span className="text-xs text-white/40 w-10 text-right">{pct.toFixed(0)}%</span>
        </div>
    )
}

export default function Subscriptions() {
    const [subs, setSubs] = useState([])
    const [cancelCandidates, setCancelCandidates] = useState([])
    const [loading, setLoading] = useState(false)
    const [cancelLoading, setCancelLoading] = useState(null)

    const maxScore = subs.reduce((m, s) => Math.max(m, s.cancel_score || 0), 1)

    const fetchSubs = async () => {
        setLoading(true)
        try {
            const res = await fetch(`${API}/api/subscriptions`)
            const data = await res.json()
            setSubs(data.subscriptions || [])
            setCancelCandidates(data.cancel_candidates || [])
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchSubs() }, [])

    const handleCancel = async (sub) => {
        setCancelLoading(sub.id)
        // Submit for approval
        try {
            const res = await fetch(`${API}/api/approve-action`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    approval_id: `cancel_${sub.id}`,
                    approved: true,
                    reason: 'User initiated cancel from subscriptions page',
                }),
            })
            alert(`Cancellation approved for ${sub.service_name}`)
            fetchSubs()
        } catch (e) {
            alert('Failed to cancel – check backend connection')
        } finally {
            setCancelLoading(null)
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Subscriptions</h1>
                    <p className="text-white/40 text-sm mt-1">Track recurring charges and find cancellation opportunities</p>
                </div>
                <button onClick={fetchSubs} className="btn-secondary text-sm">
                    <RefreshCw size={14} />
                    Refresh
                </button>
            </div>

            {/* Cancel Candidates Highlight */}
            {cancelCandidates.length > 0 && (
                <div className="glass-card border border-amber-500/30 bg-amber-500/5 p-4">
                    <h2 className="flex items-center gap-2 text-amber-400 font-semibold mb-3">
                        <AlertTriangle size={16} />
                        Top {cancelCandidates.length} Cancel Candidates
                    </h2>
                    <div className="grid gap-3">
                        {cancelCandidates.map(sub => (
                            <div key={sub.id} className="flex items-center gap-3 p-3 bg-amber-500/5 rounded-lg border border-amber-500/20">
                                <div className="flex-1">
                                    <p className="text-white font-medium text-sm">{sub.service_name}</p>
                                    <p className="text-xs text-amber-400/70 mt-0.5">
                                        ₹{sub.amount}/mo · {sub.days_since_seen} days since seen
                                        {sub.possibly_unused && ' · ⚠️ Possibly unused'}
                                    </p>
                                </div>
                                <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full border border-amber-500/30">
                                    Score: {(sub.cancel_score || 0).toFixed(0)}
                                </span>
                                <button
                                    onClick={() => handleCancel(sub)}
                                    disabled={cancelLoading === sub.id}
                                    className="btn-danger text-xs py-1.5"
                                >
                                    {cancelLoading === sub.id ? <Loader2 size={12} className="animate-spin" /> : '🚫'}
                                    Cancel
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Full Table */}
            {loading ? (
                <div className="flex justify-center py-12">
                    <Loader2 size={32} className="animate-spin text-blue-400" />
                </div>
            ) : subs.length === 0 ? (
                <div className="glass-card p-10 text-center">
                    <p className="text-white/40">No subscriptions tracked yet. Process some emails first!</p>
                </div>
            ) : (
                <div className="glass-card overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-white/5">
                                    <th className="text-left p-4 text-white/40 font-medium">Service</th>
                                    <th className="text-left p-4 text-white/40 font-medium">Amount</th>
                                    <th className="text-left p-4 text-white/40 font-medium">Cycle</th>
                                    <th className="text-left p-4 text-white/40 font-medium">Status</th>
                                    <th className="text-left p-4 text-white/40 font-medium">Days Since Seen</th>
                                    <th className="text-left p-4 text-white/40 font-medium w-40">Cancel Score</th>
                                    <th className="p-4" />
                                </tr>
                            </thead>
                            <tbody>
                                {subs.map((sub, i) => (
                                    <tr
                                        key={sub.id}
                                        className={`border-b border-white/5 hover:bg-white/3 transition-colors ${cancelCandidates.find(c => c.id === sub.id) ? 'bg-amber-500/3' : ''
                                            }`}
                                    >
                                        <td className="p-4 text-white font-medium">{sub.service_name}</td>
                                        <td className="p-4 text-emerald-400">₹{sub.amount?.toLocaleString('en-IN')}</td>
                                        <td className="p-4 text-white/50 capitalize">{sub.billing_cycle}</td>
                                        <td className="p-4">
                                            <span className={`px-2 py-0.5 rounded-full text-xs ${sub.detected_active
                                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                                    : 'bg-red-500/10 text-red-400 border border-red-500/30'
                                                }`}>
                                                {sub.detected_active ? 'Active' : 'Inactive'}
                                            </span>
                                            {sub.possibly_unused && (
                                                <span className="ml-1 px-1.5 py-0.5 rounded text-xs bg-amber-500/10 text-amber-400">unused</span>
                                            )}
                                        </td>
                                        <td className="p-4 text-white/50">{sub.days_since_seen}d</td>
                                        <td className="p-4 w-40">
                                            <CancelScoreBar score={sub.cancel_score || 0} maxScore={maxScore} />
                                        </td>
                                        <td className="p-4">
                                            {sub.possibly_unused && (
                                                <button
                                                    onClick={() => handleCancel(sub)}
                                                    disabled={cancelLoading === sub.id}
                                                    className="btn-danger text-xs py-1 px-2"
                                                >
                                                    {cancelLoading === sub.id ? <Loader2 size={11} className="animate-spin" /> : 'Cancel'}
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    )
}
