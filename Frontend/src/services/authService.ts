const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

export interface AuthCredentials {
  email: string
  password: string
}

export interface AuthResponse {
  token: string
  email: string
}

async function request(path: string, credentials: AuthCredentials): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.message ?? 'Something went wrong. Please try again.')
  }

  return response.json()
}

export function login(credentials: AuthCredentials): Promise<AuthResponse> {
  return request('/auth/login', credentials)
}

export function register(credentials: AuthCredentials): Promise<AuthResponse> {
  return request('/auth/register', credentials)
}
