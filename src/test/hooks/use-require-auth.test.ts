import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useRequireAuth } from '../../hooks/use-require-auth'
import { useAuthStore } from '../../stores/auth-store'

const navigation = {
  push: vi.fn(),
  pathname: '/dashboard',
}

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: navigation.push }),
  usePathname: () => navigation.pathname,
}))

const loggedInUser = { id: 'u1', email: 'a@b.com', name: 'A' }

describe('useRequireAuth', () => {
  beforeEach(() => {
    navigation.push.mockClear()
    navigation.pathname = '/dashboard'
    useAuthStore.setState({
      user: null,
      accessToken: null,
      isLoaded: false,
    })
  })

  it('stays in checking mode while the store is not loaded', () => {
    const { result } = renderHook(() => useRequireAuth())
    expect(result.current).toBe(false)
    expect(navigation.push).not.toHaveBeenCalled()
  })

  it('returns true for an authenticated user', () => {
    useAuthStore.setState({ user: loggedInUser, accessToken: 'token', isLoaded: true })
    const { result } = renderHook(() => useRequireAuth())
    expect(result.current).toBe(true)
    expect(navigation.push).not.toHaveBeenCalled()
  })

  it('redirects anonymous users to /login', () => {
    useAuthStore.setState({ isLoaded: true })
    const { result } = renderHook(() => useRequireAuth())
    expect(result.current).toBe(false)
    expect(navigation.push).toHaveBeenCalledWith('/login')
  })

  it('does not redirect on the login page even when anonymous', () => {
    navigation.pathname = '/login'
    useAuthStore.setState({ isLoaded: true })
    const { result } = renderHook(() => useRequireAuth())
    expect(result.current).toBe(false)
    expect(navigation.push).not.toHaveBeenCalled()
  })

  it('does not redirect on the signup page even when anonymous', () => {
    navigation.pathname = '/signup'
    useAuthStore.setState({ isLoaded: true })
    const { result } = renderHook(() => useRequireAuth())
    expect(result.current).toBe(false)
    expect(navigation.push).not.toHaveBeenCalled()
  })

  it('flips to authenticated once the store loads a user', () => {
    const { result } = renderHook(() => useRequireAuth())
    expect(result.current).toBe(false)

    act(() => {
      useAuthStore.setState({ user: loggedInUser, accessToken: 'token', isLoaded: true })
    })
    expect(result.current).toBe(true)
  })
})