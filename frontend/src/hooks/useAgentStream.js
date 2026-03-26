// Custom hook for consuming SSE streams from the agent
import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = 'http://localhost:8000'

export function useAgentStream({ autoConnect = false } = {}) {
    const [events, setEvents] = useState([])
    const [isConnected, setIsConnected] = useState(false)
    const [isRunning, setIsRunning] = useState(false)
    const [finalAnswers, setFinalAnswers] = useState([])
    const [pendingApprovals, setPendingApprovals] = useState([])
    const esRef = useRef(null)

    const appendEvent = useCallback((evt) => {
        setEvents(prev => [...prev.slice(-200), evt]) // keep last 200 events
    }, [])

    const connect = useCallback((demoMode = false) => {
        if (esRef.current) {
            esRef.current.close()
        }
        const url = demoMode
            ? `${API_BASE}/api/agent/stream/demo`
            : `${API_BASE}/api/agent/stream`

        const es = new EventSource(url)
        esRef.current = es
        setIsRunning(true)
        setEvents([])

        es.onopen = () => setIsConnected(true)

        es.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data)
                const type = data.type

                if (type === 'connected') {
                    setIsConnected(true)
                    return
                }
                if (type === 'heartbeat') return
                if (type === 'demo_complete') {
                    setIsRunning(false)
                    return
                }

                appendEvent({ ...data, ts: Date.now() })

                if (type === 'final_answer') {
                    setFinalAnswers(prev => [...prev, data.content])
                    if (!demoMode) setIsRunning(false)
                }
                if (type === 'pending_approval') {
                    setPendingApprovals(prev => {
                        const exists = prev.find(a => a.id === data.content.id)
                        return exists ? prev : [...prev, data.content]
                    })
                }
            } catch (err) {
                console.error('SSE parse error', err)
            }
        }

        es.onerror = () => {
            setIsConnected(false)
            setIsRunning(false)
            es.close()
        }
    }, [appendEvent])

    const disconnect = useCallback(() => {
        if (esRef.current) {
            esRef.current.close()
            esRef.current = null
        }
        setIsConnected(false)
        setIsRunning(false)
    }, [])

    const clearEvents = useCallback(() => {
        setEvents([])
        setFinalAnswers([])
        setPendingApprovals([])
    }, [])

    useEffect(() => {
        if (autoConnect) connect()
        return () => disconnect()
    }, [autoConnect])

    return {
        events,
        isConnected,
        isRunning,
        finalAnswers,
        pendingApprovals,
        connect,
        disconnect,
        clearEvents,
        setPendingApprovals,
    }
}
