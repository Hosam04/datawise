import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UserMenu } from '../../../components/datawise/user-menu'
import { useAuthStore } from '../../../stores/auth-store'
import { clearAllAppData } from '../../../lib/app-data'

const push = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('@/lib/app-data', () => ({
  clearAllAppData: vi.fn(),
}))

describe('UserMenu', () => {
  beforeEach(() => {
    push.mockReset()
    useAuthStore.setState({ user: { id: 'u1', name: 'Alice', email: 'a@b.com' } })
    vi.mocked(clearAllAppData).mockReset()
  })

  it('renders nothing when there is no user', () => {
    useAuthStore.setState({ user: null })
    const { container } = render(<UserMenu />)
    expect(container.innerHTML).toBe('')
  })

  it('shows the user initial in the trigger button', () => {
    render(<UserMenu />)
    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('shows the saved picture as the trigger avatar when set', () => {
    useAuthStore.setState({
      user: {
        id: 'u1',
        name: 'Alice',
        email: 'a@b.com',
        picture: '/profiles/u1-1.jpg',
      },
    })
    render(<UserMenu />)
    const trigger = screen.getByRole('button', { name: 'Account menu' })
    const img = trigger.querySelector('img')
    expect(img).toBeInTheDocument()
    expect(img?.getAttribute('src')).toContain('/profiles/u1-1.jpg')
    expect(screen.queryByText('A')).not.toBeInTheDocument()
  })

  it('falls back to the initial when the picture is empty', () => {
    useAuthStore.setState({
      user: { id: 'u1', name: 'Alice', email: 'a@b.com', picture: '' },
    })
    render(<UserMenu />)
    const trigger = screen.getByRole('button', { name: 'Account menu' })
    expect(trigger.querySelector('img')).not.toBeInTheDocument()
    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('toggles the dropdown on click and shows name + email', () => {
    render(<UserMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('a@b.com')).toBeInTheDocument()
  })

  it('opens with a keyboard shortcut and closes on Escape', () => {
    render(<UserMenu />)
    const trigger = screen.getByRole('button', { name: 'Account menu' })
    fireEvent.click(trigger)
    expect(screen.getByRole('menu')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('closes on outside click', () => {
    render(<UserMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()

    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('calls clearAllAppData and navigates to /login on logout', () => {
    render(<UserMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }))

    expect(clearAllAppData).toHaveBeenCalled()
    expect(useAuthStore.getState().user).toBeNull()
    expect(push).toHaveBeenCalledWith('/login')
  })

  it('links to the profile page and closes the menu', () => {
    render(<UserMenu />)
    fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
    const profile = screen.getByRole('menuitem', { name: 'Profile' })
    expect(profile).toHaveAttribute('href', '/profile')
    fireEvent.click(profile)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})