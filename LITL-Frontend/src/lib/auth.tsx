import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Session, SupabaseClient } from '@supabase/supabase-js'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { request, errorMessage, type Config } from './api'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/Button'

type AuthState = {
  config: Config | null; client: SupabaseClient | null; session: Session | null
  loading: boolean; error: string; retry: () => void; signOut: () => Promise<void>
  api: <T>(path: string, options?: RequestInit) => Promise<T>
}
const AuthContext = createContext<AuthState | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<Config | null>(null)
  const [client, setClient] = useState<SupabaseClient | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const pendingRequests = useRef(new Set<AbortController>())
  const identity = useRef<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    let unsubscribe: (() => void) | undefined
    setLoading(true)
    setError('')
    request<Config>('/v1/config', { signal: controller.signal }).then(async (value) => {
      if (controller.signal.aborted) return
      if (value.auth_mode === 'local' && !['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) {
        throw new Error('Unsafe configuration: local authentication is only allowed in a local browser. Configure Supabase Auth for hosted testers.')
      }
      if (value.auth_mode === 'supabase') {
        if (!value.supabase_url || !value.supabase_publishable_key) throw new Error('The API has not configured Supabase browser authentication.')
        const { createClient } = await import('@supabase/supabase-js')
        if (controller.signal.aborted) return
        const sdk = createClient(value.supabase_url, value.supabase_publishable_key)
        const { data, error: authError } = await sdk.auth.getSession()
        if (authError) throw authError
        if (controller.signal.aborted) return
        setClient(sdk)
        setSession(data.session)
        identity.current = data.session?.user.id || null
        const { data: listener } = sdk.auth.onAuthStateChange((_event, next) => {
          const nextIdentity = next?.user.id || null
          if (identity.current !== nextIdentity) {
            pendingRequests.current.forEach((request) => request.abort())
            pendingRequests.current.clear()
            identity.current = nextIdentity
          }
          setSession(next)
        })
        unsubscribe = () => listener.subscription.unsubscribe()
      } else {
        setClient(null)
        setSession(null)
      }
      setConfig(value)
      setLoading(false)
    }).catch((cause) => {
      if (!controller.signal.aborted) { setError(errorMessage(cause)); setLoading(false) }
    })
    return () => { controller.abort(); unsubscribe?.() }
  }, [attempt])
  const api = useCallback(async <T,>(path: string, options: RequestInit = {}) => {
    const controller = new AbortController()
    const abort = () => controller.abort()
    if (options.signal?.aborted) controller.abort()
    options.signal?.addEventListener('abort', abort, { once: true })
    pendingRequests.current.add(controller)
    try {
      const result = await request<T>(path, { ...options, signal: controller.signal }, client)
      controller.signal.throwIfAborted()
      return result
    } finally {
      pendingRequests.current.delete(controller)
      options.signal?.removeEventListener('abort', abort)
    }
  }, [client])
  const signOut = async () => {
    if (client) {
      const result = await client.auth.signOut({ scope: 'local' })
      if (result.error) throw result.error
      setSession(null)
    }
  }
  return <AuthContext.Provider value={{ config, client, session, loading, error, retry: () => setAttempt((n) => n + 1), signOut, api }}>{children}</AuthContext.Provider>
}
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('Auth provider missing')
  return context
}
export function ConfigGate({ children }: { children: ReactNode }) {
  const { loading, error, retry } = useAuth()
  if (loading || error) return <AppShell><div className="page narrow"><h1 className="type-h2">{loading ? 'Connecting to LiTL' : 'Connection / setup problem'}</h1><p role={error ? 'alert' : 'status'}>{error || 'Loading server configuration. Free hosting may take about a minute to wake up.'}</p>{error && <Button onClick={retry}>Retry connection</Button>}</div></AppShell>
  return children
}
export function postAuthPath(from: unknown) {
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') && from !== '/login' && from !== '/signup'
    ? from
    : '/documents'
}
export function ProtectedRoutes() {
  const { config, session } = useAuth()
  const location = useLocation()
  return <ConfigGate>{config?.auth_mode === 'supabase' && !session
    ? <Navigate to="/login" replace state={{ from: location.pathname }} />
    : <div key={session?.user.id || 'local'}><Outlet /></div>}</ConfigGate>
}
