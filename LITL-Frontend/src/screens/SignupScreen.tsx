import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ConfigGate, postAuthPath, useAuth } from '@/lib/auth'
import { errorMessage, request } from '@/lib/api'
import { AppShell } from '@/components/layout/AppShell'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

type SignupResponse = {
  user_id: string
  session: { access_token: string; refresh_token: string; expires_in: number; token_type: string } | null
}

export default function SignupScreen() {
  const { config, client, session } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const destination = postAuthPath(location.state?.from)
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!client) return
    setBusy(true)
    setError('')
    setNotice('')
    if (password !== confirm) {
      setError('Passwords do not match.')
      setBusy(false)
      return
    }
    if (password.length < 6) {
      setError('Use a password with at least 6 characters.')
      setBusy(false)
      return
    }
    try {
      const result = await request<SignupResponse>('/v1/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setPassword('')
      setConfirm('')
      if (result.session) {
        const applied = await client.auth.setSession({
          access_token: result.session.access_token,
          refresh_token: result.session.refresh_token,
        })
        if (applied.error) throw applied.error
        navigate(destination, { replace: true })
        return
      }
      setNotice('Account created. Check your email to confirm the address, then sign in.')
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setBusy(false)
    }
  }
  return (
    <ConfigGate>
      {session || config?.auth_mode === 'local' ? (
        <Navigate to={destination} replace />
      ) : (
        <AppShell>
          <div className="page narrow">
            <Card className="p-6">
              <h1 className="type-h2">Create a LiTL account</h1>
              <p className="my-4 text-slate">
                Create an email and password to upload public, synthetic or fully anonymized English Indian legal documents and record review decisions.
              </p>
              <form onSubmit={submit} className="stack">
                <label>
                  Email
                  <input required autoComplete="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
                </label>
                <label>
                  Password
                  <input required minLength={6} autoComplete="new-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
                </label>
                <label>
                  Confirm password
                  <input required minLength={6} autoComplete="new-password" type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} />
                </label>
                {error && <p role="alert" className="text-red">{error}</p>}
                {notice && <p role="status">{notice}</p>}
                <Button type="submit" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</Button>
              </form>
              <p className="mt-4 text-slate">
                Already have an account? <Link to="/login" state={location.state} className="font-semibold text-ink underline">Sign in</Link>
              </p>
            </Card>
          </div>
        </AppShell>
      )}
    </ConfigGate>
  )
}
