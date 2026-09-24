import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/components/datawise/route-error', () => ({
  RouteError: ({ title, error }: { title: string; error: Error }) => (
    <div data-testid="route-error" data-title={title} data-msg={error.message}>
      {title}
    </div>
  ),
}))
vi.mock('@/components/datawise/route-loading', () => ({
  DashboardPageLoading: () => <div data-testid="dash-loading" />,
  ChatPageLoading: () => <div data-testid="chat-loading" />,
  ListPageLoading: () => <div data-testid="list-loading" />,
  DetailPageLoading: () => <div data-testid="detail-loading" />,
  UploadPageLoading: () => <div data-testid="upload-loading" />,
  SettingsPageLoading: () => <div data-testid="settings-loading" />,
  ProfilePageLoading: () => <div data-testid="profile-loading" />,
}))
vi.mock('@/components/datawise/not-found-view', () => ({
  NotFoundView: ({ title }: { title: string }) => (
    <div data-testid="not-found" data-title={title}>
      {title}
    </div>
  ),
}))

describe('dashboard route error wrappers', () => {
  const cases = [
    { path: '@/app/(dashboard)/error', title: 'Dashboard error' },
    { path: '@/app/(dashboard)/chat/error', title: 'Chat error' },
    { path: '@/app/(dashboard)/datasets/[id]/error', title: 'Dataset error' },
  ]

  for (const c of cases) {
    it(`renders ${c.path} with its title`, async () => {
      const mod = await import(c.path)
      const Wrapper = mod.default
      render(<Wrapper error={new Error('boom')} reset={() => {}} />)
      expect(screen.getByTestId('route-error')).toHaveAttribute('data-title', c.title)
      expect(screen.getByTestId('route-error')).toHaveAttribute('data-msg', 'boom')
    })
  }
})

describe('dashboard route loading wrappers', () => {
  const cases = [
    { path: '@/app/(dashboard)/loading', testid: 'dash-loading' },
    { path: '@/app/(dashboard)/chat/loading', testid: 'chat-loading' },
    { path: '@/app/(dashboard)/datasets/loading', testid: 'list-loading' },
    { path: '@/app/(dashboard)/datasets/[id]/loading', testid: 'detail-loading' },
    { path: '@/app/(dashboard)/reports/loading', testid: 'list-loading' },
    { path: '@/app/(dashboard)/reports/[id]/loading', testid: 'detail-loading' },
    { path: '@/app/(dashboard)/favorites/loading', testid: 'list-loading' },
    { path: '@/app/(dashboard)/profile/loading', testid: 'profile-loading' },
    { path: '@/app/(dashboard)/settings/loading', testid: 'settings-loading' },
    { path: '@/app/(dashboard)/upload/loading', testid: 'upload-loading' },
  ]

  for (const c of cases) {
    it(`renders ${c.path}`, async () => {
      const mod = await import(c.path)
      const Wrapper = mod.default
      render(<Wrapper />)
      expect(screen.getByTestId(c.testid)).toBeInTheDocument()
    })
  }
})

describe('dashboard route not-found wrappers', () => {
  const cases = [
    { path: '@/app/(dashboard)/not-found', title: 'Page not found' },
    { path: '@/app/(dashboard)/chat/not-found', title: 'Chat not found' },
    { path: '@/app/(dashboard)/datasets/not-found', title: 'Datasets page not found' },
    { path: '@/app/(dashboard)/datasets/[id]/not-found', title: 'Dataset not found' },
    { path: '@/app/(dashboard)/reports/not-found', title: 'Reports page not found' },
    { path: '@/app/(dashboard)/reports/[id]/not-found', title: 'Report not found' },
    { path: '@/app/(dashboard)/favorites/not-found', title: 'Favorites not found' },
    { path: '@/app/(dashboard)/profile/not-found', title: 'Profile not found' },
    { path: '@/app/(dashboard)/settings/not-found', title: 'Settings not found' },
    { path: '@/app/(dashboard)/upload/not-found', title: 'Upload not found' },
  ]

  for (const c of cases) {
    it(`renders ${c.path} with its title`, async () => {
      const mod = await import(c.path)
      const Wrapper = mod.default
      render(<Wrapper />)
      expect(screen.getByTestId('not-found')).toHaveAttribute('data-title', c.title)
    })
  }
})