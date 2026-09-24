import { beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '../../stores/auth-store'

beforeEach(() => {
  useAuthStore.setState({
    user: null,
    accessToken: null,
    isLoaded: false,
  })
  localStorage.clear()
})

describe('auth-store actions', () => {
  it('starts unauthenticated and not loaded', () => {
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.accessToken).toBeNull()
    expect(state.isLoaded).toBe(false)
  })

  it('setUser / setAccessToken / setIsLoaded update state', () => {
    const { setUser, setAccessToken, setIsLoaded } = useAuthStore.getState()
    setUser({ email: 'a@b.com', name: 'A' })
    setAccessToken('tok')
    setIsLoaded(true)
    expect(useAuthStore.getState().user).toEqual({ email: 'a@b.com', name: 'A' })
    expect(useAuthStore.getState().accessToken).toBe('tok')
    expect(useAuthStore.getState().isLoaded).toBe(true)
  })

  it('isAuthenticated requires both an email-bearing user and a token', () => {
    const store = useAuthStore.getState()
    expect(store.isAuthenticated()).toBe(false)

    useAuthStore.setState({ user: { email: 'a@b.com', name: 'A' }, accessToken: null })
    expect(useAuthStore.getState().isAuthenticated()).toBe(false)

    useAuthStore.setState({ user: { email: 'a@b.com', name: 'A' }, accessToken: 'tok' })
    expect(useAuthStore.getState().isAuthenticated()).toBe(true)

    useAuthStore.setState({ user: { name: 'No Email' }, accessToken: 'tok' })
    expect(useAuthStore.getState().isAuthenticated()).toBe(false)
  })

  it('logout clears user and token but keeps isLoaded', () => {
    useAuthStore.setState({
      user: { email: 'a@b.com', name: 'A' },
      accessToken: 'tok',
      isLoaded: true,
    })
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().user).toBeNull()
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().isLoaded).toBe(true)
  })
})

describe('auth-store persistence', () => {
  it('does not persist isLoaded (runtime flag only)', async () => {
    useAuthStore.setState({
      user: { email: 'a@b.com', name: 'A' },
      accessToken: 'tok',
      isLoaded: true,
    })
    const persisted = JSON.parse(localStorage.getItem('datawise-auth') ?? '{}')
    expect(persisted.state.user).toEqual({ email: 'a@b.com', name: 'A' })
    expect(persisted.state.accessToken).toBe('tok')
    expect(persisted.state).not.toHaveProperty('isLoaded')
  })

  it('rehydrates the user and marks the store loaded via onRehydrateStorage', async () => {
    const persisted = {
      state: {
        user: { email: 'persisted@example.com', name: 'P' },
        accessToken: 'persisted-token',
      },
      version: 0,
    }
    localStorage.setItem('datawise-auth', JSON.stringify(persisted))

    await useAuthStore.persist.rehydrate()

    expect(useAuthStore.getState().user).toEqual({
      email: 'persisted@example.com',
      name: 'P',
    })
    expect(useAuthStore.getState().accessToken).toBe('persisted-token')
    expect(useAuthStore.getState().isLoaded).toBe(true)
  })
})