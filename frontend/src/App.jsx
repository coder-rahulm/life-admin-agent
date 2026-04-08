import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, CreditCard, BarChart3, Play, Loader2 } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import Subscriptions from './pages/Subscriptions'
import Insights from './pages/Insights'
import ChatBot from './components/ChatBot'

const API = 'http://localhost:8000'

function Navbar({ onStartDemo, demoRunning }) {
    return (
        <nav className="sticky top-0 z-50 border-b border-white/5 backdrop-blur bg-white/3">
            <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="text-xl">🤖</span>
                    <span className="font-bold text-white">Life Admin Agent</span>
                    {/* <span className="text-xs text-white/30 hidden md:inline">Powered by Claude + ReAct</span> */}
                </div>

                <div className="flex items-center gap-1">
                    <NavLink
                        to="/"
                        end
                        className={({ isActive }) =>
                            `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${isActive ? 'bg-blue-600/30 text-blue-300' : 'text-white/50 hover:text-white hover:bg-white/5'
                            }`
                        }
                    >
                        <LayoutDashboard size={14} />
                        <span className="hidden md:inline">Dashboard</span>
                    </NavLink>
                    <NavLink
                        to="/subscriptions"
                        className={({ isActive }) =>
                            `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${isActive ? 'bg-blue-600/30 text-blue-300' : 'text-white/50 hover:text-white hover:bg-white/5'
                            }`
                        }
                    >
                        <CreditCard size={14} />
                        <span className="hidden md:inline">Subscriptions</span>
                    </NavLink>
                    <NavLink
                        to="/insights"
                        className={({ isActive }) =>
                            `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${isActive ? 'bg-blue-600/30 text-blue-300' : 'text-white/50 hover:text-white hover:bg-white/5'
                            }`
                        }
                    >
                        <BarChart3 size={14} />
                        <span className="hidden md:inline">Insights</span>
                    </NavLink>
                </div>

                {/* Start Demo button — hidden for project review
                <button
                    onClick={onStartDemo}
                    disabled={demoRunning}
                    className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white text-sm font-medium rounded-lg transition-all shadow-lg disabled:opacity-60"
                >
                    {demoRunning
                        ? <Loader2 size={13} className="animate-spin" />
                        : <Play size={13} fill="currentColor" />}
                    {demoRunning ? 'Running...' : '▶️ Start Demo'}
                </button>
                */}
            </div>
        </nav>
    )
}

export default function App() {
    const [demoRunning, setDemoRunning] = useState(false)

    const handleStartDemo = async () => {
        if (demoRunning) return
        setDemoRunning(true)
        try {
            // Trigger email processing which feeds into SSE stream
            await fetch(`${API}/api/process-emails`, { method: 'POST' })
        } catch (e) {
            console.error(e)
        } finally {
            setTimeout(() => setDemoRunning(false), 10000)
        }
    }

    return (
        <BrowserRouter>
            <div className="min-h-screen">
                <Navbar onStartDemo={handleStartDemo} demoRunning={demoRunning} />
                <main className="max-w-6xl mx-auto px-4 py-6">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/subscriptions" element={<Subscriptions />} />
                        <Route path="/insights" element={<Insights />} />
                    </Routes>
                </main>
                <ChatBot />
            </div>
        </BrowserRouter>
    )
}
