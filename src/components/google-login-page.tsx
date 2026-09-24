'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/stores/auth-store'
import { hydrateUserDataFromServer } from '@/lib/hydrate-user-data'
import {
  clearGoogleIdentityCallback,
  initializeGoogleIdentity,
  loadGoogleIdentityServices,
  renderGoogleSignInButton,
} from '@/lib/google-identity'


interface GoogleLoginPageProps {
  googleClientId: string
}

export default function GoogleLoginPage({ googleClientId }: GoogleLoginPageProps) {
  const router = useRouter()
  const { setUser, setTokens } = useAuthStore()
  const googleButtonRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!googleClientId) {
      setError('Please configure GOOGLE_CLIENT_ID in your environment variables.')
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
          setError(typeof data.detail === 'string' ? data.detail : 'Google sign-in failed on server')
          return
        }

        setUser({
          id: data.user?.id,
          name: data.user?.name,
          email: data.user?.email,
          picture: data.user?.picture,
        })
        setTokens(data.tokens?.access_token ?? null, data.tokens?.refresh_token ?? null)
        await hydrateUserDataFromServer()
        router.push('/')
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : 'An unexpected error occurred while signing in.')
      }
    }

    loadGoogleIdentityServices()
      .then(() => {
        if (cancelled) return
        const ready = initializeGoogleIdentity(googleClientId, handleGoogleCredential)
        if (!ready) {
          setError('Google Sign-In is currently unavailable. Please refresh the page.')
          return
        }

        if (googleButtonRef.current) {
          renderGoogleSignInButton(googleButtonRef.current, { width: 400 })
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
  }, [googleClientId, router, setUser, setTokens])



  return (
    <main className="flex min-h-screen items-center justify-center bg-linear-to-br from-background to-background/80 px-4 py-12 text-foreground">
      <div className="w-full max-w-2xl rounded-2xl border border-border bg-card p-8 shadow-xl shadow-black/5 backdrop-blur-sm">
        <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div className="space-y-6">
            <div className="max-w-xl space-y-4">
              <p className="text-xs font-bold uppercase tracking-widest text-primary">DataWise</p>
              <h1 className="text-4xl font-bold text-foreground sm:text-5xl">
                Sign In
              </h1>
              <p className="text-base text-muted-foreground leading-relaxed">
                Access your data analytics dashboard using your Google account. Manage datasets, view reports, and track your activity all in one place.
              </p>
            </div>

            <div className="space-y-4 pt-2">
              <div
                ref={googleButtonRef}
                className="flex min-h-10 w-full justify-center overflow-hidden rounded-lg"
                aria-label="Sign in with Google"
              />
            </div>

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                {error}
              </div>
            ) : null}
          </div>

          <div className="hidden lg:flex flex-col rounded-xl bg-linear-to-b from-primary/10 to-primary/5 p-8 text-center ring-1 ring-primary/20">
            <p className="text-xl font-bold text-foreground mb-6">What You&apos;ll Get</p>
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