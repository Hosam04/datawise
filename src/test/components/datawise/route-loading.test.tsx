import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  DashboardPageLoading,
  ListPageLoading,
  DetailPageLoading,
  ChatPageLoading,
  UploadPageLoading,
  SettingsPageLoading,
} from '../../../components/datawise/route-loading'

describe.each([
  ['DashboardPageLoading', DashboardPageLoading],
  ['ListPageLoading', ListPageLoading],
  ['DetailPageLoading', DetailPageLoading],
  ['ChatPageLoading', ChatPageLoading],
  ['UploadPageLoading', UploadPageLoading],
  ['SettingsPageLoading', SettingsPageLoading],
])('%s', (_name, Component) => {
  it('renders a busy loading shell with an accessible label', () => {
    const { container } = render(<Component />)
    const shell = container.querySelector('[aria-busy="true"]')
    expect(shell).not.toBeNull()
    expect(shell).toHaveAttribute('aria-label', 'Loading page')
  })

  it('renders skeletons', () => {
    const { container } = render(<Component />)
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull()
  })
})