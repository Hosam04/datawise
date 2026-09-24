import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import GoogleLoginPage from '../../components/google-login-page'
import { useAuthStore } from '../../stores/auth-store'

const pushMock = vi.fn()
const loadMock = vi.fn()
const initMock = vi.fn()
const renderButtonMock = vi.fn()
const clearCallbackMock = vi.fn()
let credentialCallback: ((response: { credential: string }) => void) | undefined

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/lib/hydrate-user-data', () => ({
  hydrateUserDataFromServer: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/lib/google-identity', () => ({
  loadGoogleIdentityServices: (...args: unknown[]) => loadMock(...args),
  initializeGoogleIdentity: (clientId: string, cb: (r: { credential: string }) => void) => {
    credentialCallback = cb
    return initMock(clientId, cb)
  },
  renderGoogleSignInButton: (...args: unknown[]) => renderButtonMock(...args),
  clearGoogleIdentityCallback: (...args: unknown[]) => clearCallbackMock(...args),
}))

describe('GoogleLoginPage', () => {
  beforeEach(() => {
    pushMock.mockReset()
    loadMock.mockReset()
    initMock.mockReset()
    renderButtonMock.mockReset()
    clearCallbackMock.mockReset()
    credentialCallback = undefined
    loadMock.mockResolvedValue({})
    initMock.mockReturnValue(true)
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null })
  })

  it('shows the misconfiguration error when no client id is provided', () => {
    render(<GoogleLoginPage googleClientId="" />)
    expect(
      screen.getByText(/Please configure GOOGLE_CLIENT_ID/),
    ).toBeInTheDocument()
    // GSI renders into a labeled container, not a native button
    expect(screen.getByLabelText('Sign in with Google')).toBeInTheDocument()
  })

  it('loads Google Identity and renders the sign-in button when client id is set', async () => {
    render(<GoogleLoginPage googleClientId="abc" />)
    await waitFor(() => {
      expect(loadMock).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(initMock).toHaveBeenCalledWith('abc', expect.any(Function))
      expect(renderButtonMock).toHaveBeenCalled()
    })
    expect(screen.getByLabelText('Sign in with Google')).toBeInTheDocument()
  })

  it('signs in, stores the user, and navigates to the dashboard', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        user: { name: 'Ada', email: 'ada@example.com' },
        tokens: { access_token: 'token-1', refresh_token: 'ref-1' },
      }),
    } as Response)

    render(<GoogleLoginPage googleClientId="abc" />)
    await waitFor(() => {
      expect(credentialCallback).toBeTypeOf('function')
    })

    await credentialCallback!({ credential: 'id-token-xyz' })

    await waitFor(() => {
      expect(useAuthStore.getState().user).toMatchObject({
        name: 'Ada',
        email: 'ada@example.com',
      })
      expect(useAuthStore.getState().accessToken).toBe('token-1')
      expect(pushMock).toHaveBeenCalledWith('/')
    })
    fetchMock.mockRestore()
  })

  it('shows the error provided by the backend', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'You declined the sign in.' }),
    } as Response)

    render(<GoogleLoginPage googleClientId="abc" />)
    await waitFor(() => {
      expect(credentialCallback).toBeTypeOf('function')
    })

    await credentialCallback!({ credential: 'bad' })

    expect(await screen.findByText('You declined the sign in.')).toBeInTheDocument()
    expect(pushMock).not.toHaveBeenCalled()
  })
})