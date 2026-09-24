import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SignupPage from '../../../app/signup/page'
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

describe('SignupPage', () => {
  beforeEach(() => {
    router.push.mockClear()
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null })
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function fillForm(over: { email?: string; password?: string; confirm?: string; name?: string } = {}) {
    fireEvent.change(screen.getByLabelText('Full Name'), { target: { value: over.name ?? 'Alice' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: over.email ?? 'a@b.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: over.password ?? 'password123' } })
    fireEvent.change(screen.getByLabelText('Confirm Password'), {
      target: { value: over.confirm ?? 'password123' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /Create Account/ }).closest('form')!)
  }

  it('renders the sign-up form', () => {
    render(<SignupPage />)
    expect(screen.getByRole('heading', { name: 'Create Account' })).toBeInTheDocument()
    expect(screen.getByLabelText('Full Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })

  it('rejects an invalid email', async () => {
    render(<SignupPage />)
    fillForm({ email: 'not-an-email' })
    expect(await screen.findByText('Please enter a valid email address')).toBeInTheDocument()
    expect(router.push).not.toHaveBeenCalled()
  })

  it('rejects mismatched passwords', async () => {
    render(<SignupPage />)
    fillForm({ confirm: 'different' })
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
    expect(router.push).not.toHaveBeenCalled()
  })

  it('rejects a short password', async () => {
    render(<SignupPage />)
    fillForm({ password: 'abc', confirm: 'abc' })
    expect(await screen.findByText('Password must be at least 6 characters')).toBeInTheDocument()
    expect(router.push).not.toHaveBeenCalled()
  })

  it('creates an account and redirects to the dashboard', async () => {
    // Signup calls /auth/register then /auth/login — both must succeed
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        user: { email: 'a@b.com', name: 'Alice' },
        tokens: { access_token: 'tok', refresh_token: 'ref' },
      }),
    } as unknown as Response)
    render(<SignupPage />)
    fillForm()
    await waitFor(() => {
      expect(useAuthStore.getState().user).toMatchObject({
        email: 'a@b.com',
        name: 'Alice',
      })
    })
    expect(useAuthStore.getState().accessToken).toBe('tok')
    expect(router.push).toHaveBeenCalledWith('/')
  })

  it('shows the server error when signup fails', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      json: async () => ({ error: 'Email already registered' }),
    } as unknown as Response)
    render(<SignupPage />)
    fillForm()
    expect(await screen.findByText('Email already registered')).toBeInTheDocument()
    expect(router.push).not.toHaveBeenCalled()
  })
})