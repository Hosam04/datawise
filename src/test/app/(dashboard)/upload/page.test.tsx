import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import UploadPage from '../../../../app/(dashboard)/upload/page'

vi.mock('@/components/upload/upload-panel', () => ({
  UploadPanel: () => <div data-testid="upload-panel" />,
}))
vi.mock('@/components/datawise/page-header', () => ({
  PageHeader: ({ title }: { title: string }) => <header>{title}</header>,
}))

describe('UploadPage', () => {
  it('renders the page header and upload panel', () => {
    render(<UploadPage />)
    expect(screen.getByText('Upload Dataset')).toBeInTheDocument()
    expect(screen.getByTestId('upload-panel')).toBeInTheDocument()
  })
})