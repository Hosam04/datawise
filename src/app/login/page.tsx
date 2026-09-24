'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Mail, Lock } from 'lucide-react'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'
import { hydrateUserDataFromServer } from '@/lib/hydrate-user-data'
import {
  clearGoogleIdentityCallback,
  initializeGoogleIdentity,
  loadGoogleIdentityServices,
  renderGoogleSignInButton,
} from '@/lib/google-identity'

export default function LoginPage() {
  const router = useRouter()
  const { setUser, setTokens } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const googleButtonRef = useRef<HTMLDivElement>(null)

  const validateEmail = (emailValue: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailRegex.test(emailValue)
  }

  // Load and initialize Google Identity Services through a shared singleton.
  useEffect(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''
    if (!clientId) {
      setError('Google Sign-In is not configured. Please check NEXT_PUBLIC_GOOGLE_CLIENT_ID.')
      return
    }

    let cancelled = false

    const handleGoogleCredential = async (response: { credential: string }) => {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'
        const backendRes = await fetch(`${API_URL}/auth/google`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: response.credential }),
        })
        const data = await backendRes.json()

        if (!backendRes.ok) {
          setError(typeof data.detail === 'string' ? data.detail : 'Google sign-in failed')
          return
        }

        setUser({
          id: data.user?.id,
          name: data.user?.name,
          email: data.user?.email,
          picture: data.user?.picture,
        })
        setTokens(
          data.tokens?.access_token ?? null,
          data.tokens?.refresh_token ?? null,
        )
        await hydrateUserDataFromServer()
        router.push('/')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to process Google sign-in')
      }
    }

    loadGoogleIdentityServices()
      .then(() => {
        if (cancelled) return
        const ready = initializeGoogleIdentity(clientId, handleGoogleCredential)
        if (!ready) {
          setError('Google Sign-In is currently unavailable. Please refresh the page.')
          return
        }

        if (googleButtonRef.current) {
          renderGoogleSignInButton(googleButtonRef.current, {
            width: 400,
          })
        }
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load Google Sign-In library.')
      })

    return () => {
      cancelled = true
      clearGoogleIdentityCallback(handleGoogleCredential)
    }
  }, [setUser, setTokens, router])

  const handleLocalLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!validateEmail(email)) {
      setError('Please enter a valid email address')
      return
    }

    setIsLoading(true)

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        setError(
          typeof data.detail === 'string'
            ? data.detail
            : data.error || 'Login failed',
        )
        return
      }

      setUser({
        id: data.user?.id,
        email: data.user.email,
        name: data.user.name,
        picture: data.user.picture,
      })
      setTokens(
        data.tokens?.access_token ?? null,
        data.tokens?.refresh_token ?? null,
      )
      await hydrateUserDataFromServer()
      router.push('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsLoading(false)
    }
  }



  return (
    <main className="flex min-h-screen items-center justify-center bg-linear-to-br from-background to-background/80 px-4 py-12 text-foreground">
      <div className="w-full max-w-2xl rounded-2xl border border-border bg-card p-8 shadow-xl shadow-black/5 backdrop-blur-sm">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div className="space-y-6">
            <div className="max-w-xl space-y-4">
              <p className="text-xs font-bold uppercase tracking-widest text-primary">DataWise</p>
              <h1 className="text-4xl font-bold text-foreground sm:text-5xl">Sign In</h1>
              <p className="text-base text-muted-foreground leading-relaxed">
                Access your data analytics dashboard using your Google account or email.
              </p>
            </div>

            <div className="space-y-4 pt-2">
              <div
                ref={googleButtonRef}
                className="flex min-h-10 w-full justify-center overflow-hidden rounded-lg"
                aria-label="Sign in with Google"
              />

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">Or continue with email</span>
                </div>
              </div>

              <form onSubmit={handleLocalLogin} className="space-y-3">
                <div className="space-y-2">
                  <label htmlFor="email" className="block text-sm font-medium text-foreground">
                    Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-3 size-4 text-muted-foreground" />
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder=""
                      className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="password" className="block text-sm font-medium text-foreground">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 size-4 text-muted-foreground" />
                    <input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder=""
                      className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className={cn(
                    buttonVariants({ variant: 'outline', size: 'lg' }),
                    'w-full justify-center font-semibold',
                  )}
                >
                  {isLoading ? 'Signing in...' : 'Sign in with Email'}
                </button>
              </form>

              <p className="text-center text-sm text-muted-foreground">
                Don't have an account?{' '}
                <Link href="/signup" className="font-medium text-primary hover:underline">
                  Sign up
                </Link>
              </p>
            </div>

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                {error}
              </div>
            ) : null}
          </div>

          <div className="hidden lg:flex flex-col rounded-xl bg-linear-to-b from-primary/10 to-primary/5 p-8 text-center ring-1 ring-primary/20">
            <p className="text-xl font-bold text-foreground mb-6">What You'll Get</p>
            <ul className="space-y-4 text-start text-sm text-muted-foreground">
              <li className="flex gap-3">
                <span className="text-primary font-semibold">✓</span>
                <span>Quick access to your datasets and reports</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary font-semibold">✓</span>
                <span>Secure authentication with your Google account</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary font-semibold">✓</span>
                <span>Complete control over your activities and settings</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  )
}