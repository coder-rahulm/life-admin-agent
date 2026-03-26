import React, { useState, useEffect } from 'react'
import {
    AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend,
} from 'recharts'
import { Loader2, RefreshCw, Lightbulb, ExternalLink } from 'lucide-react'

const API = 'http://localhost:8000'

const PRIORITY_COLORS = {
    P1: '#ef4444',
    P2: '#f59e0b',
    P3: '#3b82f6',
    Done: '#10b981',
}

function SparkCard({ title, children }) {
    return (
        <div className="glass-card p-5">
            <h3 className="text-white/60 text-sm font-medium mb-4">{title}</h3>
            {children}
        </div>
    )
}

export default function Insights() {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(false)
    const [tasks, setTasks] = useState([])

    const fetchData = async () => {
        setLoading(true)
        try {
            const [insRes, taskRes] = await Promise.all([
                fetch(`${API}/api/insights`),
                fetch(`${API}/api/tasks`),
            ])
            setData(await insRes.json())
            const td = await taskRes.json()
            setTasks(td.tasks || [])
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchData() }, [])

    const spendData = data?.spend_by_month || []

    const donutData = data
        ? [
            { name: 'P1', value: data.p1_count || 0 },
            { name: 'P2', value: data.p2_count || 0 },
            { name: 'P3', value: data.p3_count || 0 },
            { name: 'Done', value: data.done_tasks || 0 },
        ].filter(d => d.value > 0)
        : []

    if (loading) {
        return (
            <div className="flex justify-center py-20">
                <Loader2 size={32} className="animate-spin text-blue-400" />
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white">Insights</h1>
                    <p className="text-white/40 text-sm mt-1">Spending trends, task analytics, and agent suggestions</p>
                </div>
                <button onClick={fetchData} className="btn-secondary text-sm">
                    <RefreshCw size={14} />
                    Refresh
                </button>
            </div>

            {/* KPI row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                    { label: 'Emails Processed', value: data?.emails_processed || 0, icon: '📧' },
                    { label: 'Completion Rate', value: `${data?.completion_rate || 0}%`, icon: '✅' },
                    { label: 'Monthly Spend', value: `₹${(data?.monthly_spend || 0).toLocaleString('en-IN')}`, icon: '💰' },
                    { label: 'Unused Spend', value: `₹${(data?.unused_spend || 0).toLocaleString('en-IN')}`, icon: '🗑️' },
                ].map(kpi => (
                    <div key={kpi.label} className="stat-card">
                        <span className="text-xl">{kpi.icon}</span>
                        <div>
                            <p className="text-2xl font-bold text-white">{kpi.value}</p>
                            <p className="text-xs text-white/40">{kpi.label}</p>
                        </div>
                    </div>
                ))}
            </div>

            <div className="grid md:grid-cols-2 gap-6">
                {/* Spend Sparkline */}
                <SparkCard title="Monthly Spend (last 3 months)">
                    {spendData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={160}>
                            <AreaChart data={spendData}>
                                <defs>
                                    <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <XAxis dataKey="month" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                                <Tooltip
                                    contentStyle={{ background: '#1a2235', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                                    labelStyle={{ color: '#fff' }}
                                    formatter={(v) => [`₹${v.toLocaleString('en-IN')}`, 'Spend']}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="spend"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    fill="url(#spendGrad)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-40 flex items-center justify-center text-white/30 text-sm">
                            No spend data yet
                        </div>
                    )}
                </SparkCard>

                {/* Task Donut */}
                <SparkCard title="Task Completion Rate">
                    {donutData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={160}>
                            <PieChart>
                                <Pie
                                    data={donutData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={45}
                                    outerRadius={65}
                                    paddingAngle={3}
                                    dataKey="value"
                                >
                                    {donutData.map(entry => (
                                        <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name] || '#6b7280'} />
                                    ))}
                                </Pie>
                                <Legend
                                    formatter={(value) => <span style={{ color: '#9ca3af', fontSize: 11 }}>{value}</span>}
                                />
                                <Tooltip
                                    contentStyle={{ background: '#1a2235', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                                    labelStyle={{ color: '#fff' }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="h-40 flex items-center justify-center text-white/30 text-sm">
                            No tasks yet
                        </div>
                    )}
                </SparkCard>
            </div>

            {/* Agent Suggestions */}
            {data?.suggestions?.length > 0 && (
                <div className="glass-card p-5">
                    <h3 className="flex items-center gap-2 text-white font-semibold mb-4">
                        <Lightbulb size={16} className="text-amber-400" />
                        Agent Suggestions This Week
                    </h3>
                    <div className="space-y-3">
                        {data.suggestions.map((s, i) => (
                            <div
                                key={i}
                                className="flex items-start gap-3 p-3 bg-white/3 rounded-lg hover:bg-white/5 transition-colors cursor-pointer group"
                            >
                                <span className="text-amber-400 text-sm font-bold shrink-0">{i + 1}</span>
                                <p className="text-white/70 text-sm leading-relaxed flex-1">{s}</p>
                                <ExternalLink size={13} className="text-white/20 group-hover:text-white/50 transition-colors shrink-0 mt-0.5" />
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Recent Tasks */}
            {tasks.length > 0 && (
                <div className="glass-card p-5">
                    <h3 className="text-white font-semibold mb-4">Recent Tasks</h3>
                    <div className="space-y-2">
                        {tasks.slice(0, 5).map(t => (
                            <div key={t.id} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
                                <span className={t.priority === 'P1' ? 'badge-p1' : t.priority === 'P2' ? 'badge-p2' : 'badge-p3'}>
                                    {t.priority}
                                </span>
                                <span className="text-white/70 text-sm flex-1 truncate">{t.title}</span>
                                <span className={`text-xs ${t.status === 'done' ? 'text-emerald-400' : 'text-white/30'}`}>
                                    {t.status}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
