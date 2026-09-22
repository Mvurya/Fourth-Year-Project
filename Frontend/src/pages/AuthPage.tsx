import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../services/authService'
import './AuthPage.css'

function AuthPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loadingAction, setLoadingAction] = useState<'login' | 'register' | null>(null)

  const validate = (): boolean => {
    if (!email.trim() || !password) {
      setError('Please enter both email and password.')
      return false
    }
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setError('Please enter a valid email address.')
      return false
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.')
      return false
    }
    setError(null)
    return true
  }

  const handleSubmit = async (action: 'login' | 'register') => {
    if (!validate()) return

    setLoadingAction(action)
    setError(null)
    try {
      const authRequest = action === 'login' ? login : register
      const result = await authRequest({ email, password })
      localStorage.setItem('authToken', result.token)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoadingAction(null)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Cashflow Predictor</h1>
        <p className="auth-subtitle">Log in or create an account to continue</p>

        <form
          onSubmit={(event) => {
            event.preventDefault()
            handleSubmit('login')
          }}
          noValidate
        >
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter your password"
            autoComplete="current-password"
            required
          />

          {error && <p className="auth-error">{error}</p>}

          <div className="auth-actions">
            <button type="submit" className="auth-button primary" disabled={loadingAction !== null}>
              {loadingAction === 'login' ? 'Logging in…' : 'Log In'}
            </button>
            <button
              type="button"
              className="auth-button secondary"
              disabled={loadingAction !== null}
              onClick={() => handleSubmit('register')}
            >
              {loadingAction === 'register' ? 'Registering…' : 'Register'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default AuthPage
