import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ConfigGate, useAuth } from '@/lib/auth'
import { errorMessage } from '@/lib/api'
import { AppShell } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

export default function LoginScreen() {
  const { config, client, session } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const requested = location.state?.from
  const destination = typeof requested === 'string' && requested.startsWith('/') && !requested.startsWith('//') && requested !== '/login' ? requested : '/documents'
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!client) return
    setBusy(true); setError('')
    try {
      const result = await client.auth.signInWithPassword({ email, password })
      if (result.error) throw result.error
      setPassword('')
      navigate(destination, { replace: true })
    } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }
  return <ConfigGate>{session || config?.auth_mode === 'local' ? <Navigate to={destination} replace /> : <AppShell><div className="page narrow"><Card className="p-6"><h1 className="type-h2">Sign in to LiTL</h1><p className="my-4 text-slate">Limited beta for manually provisioned tester accounts. No public signup. Contact your beta administrator for access or password recovery.</p><form onSubmit={submit} className="stack"><label>Email<input required autoComplete="username" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><label>Password<input required autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>{error && <p role="alert" className="text-red">{error}</p>}<Button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</Button></form></Card></div></AppShell>}</ConfigGate>
}
