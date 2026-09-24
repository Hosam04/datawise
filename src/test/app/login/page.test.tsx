import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import LoginPage from '../../../app/login/page'
import { useAuthStore } from '../../../stores/auth-store'

const router = { push: vi.fn() }

vi.mock('next/navigation', () => ({
  useRouter: () => router,
}))

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}))

vi.mock('@/components/ui/button', () => ({ buttonVariants: () => 'btn' }))
vi.mock('@/lib/utils', () => ({ cn: (...args: unknown[]) => args.filter(Boolean).join(' ') }))
vi.mock('@/lib/hydrate-user-data', () => ({
  hydrateUserDataFromServer: vi.fn().mockResolvedValue(undefined),
}))

describe('LoginPage', () => {
  beforeEach(() => {
    router.push.mockClear()
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function fillForm(email: string, password: string) {
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } })
    fireEvent.submit(screen.getByRole('button', { name: /Sign in with Email/ }).closest('form')!)
  }

  it('renders the sign-in form', () => {
    render(<LoginPage />)
    expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    // Google control is a container div, not a native button
    expect(screen.getByLabelText('Sign in with Google')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign up' })).toHaveAttribute('href', '/signup')
  })

  it('rejects an invalid email', async () => {
    render(<LoginPage />)
    fillForm('not-an-email', 'password123')
    expect(await screen.findByText('Please enter a valid email address')).toBeInTheDocument()
    expect(router.push).not.toHaveBeenCalled()
  })

  it('logs in and redirects to the dashboard on success', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        user: { email: 'a@b.com', name: 'Alice' },
        tokens: { access_token: 'tok', refresh_token: 'ref' },
      }),
    } as unknown as Response)
    render(<LoginPage />)
    fillForm('a@b.com', 'password123')
    await waitFor(() => {
      expect(useAuthStore.getState().user).toMatchObject({
        email: 'a@b.com',
        name: 'Alice',
      })
    })
    expect(useAuthStore.getState().accessToken).toBe('tok')
    expect(router.push).toHaveBeenCalledWith('/')
  })

  it('shows the server error when login fails', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      json: async () => ({ error: 'Invalid credentials' }),
    } as unknown as Response)
    render(<LoginPage />)
    fillForm('a@b.com', 'wrong')
    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument()
    expect(router.push).not.toHaveBeenCalled()
  })

  it('shows a message when Google Sign-In is not configured', async () => {
    render(<LoginPage />)
    expect(
      await screen.findByText(
        'Google Sign-In is not configured. Please check NEXT_PUBLIC_GOOGLE_CLIENT_ID.',
      ),
    ).toBeInTheDocument()
  })
})