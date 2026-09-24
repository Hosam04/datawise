import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UploadValidationAlert } from '../../../components/upload/upload-validation-alert'

describe('UploadValidationAlert', () => {
  it('shows the unsupported type title and message', () => {
    render(
      <UploadValidationAlert
        error="unsupported"
        message="Only CSV, XLSX, XLS, and JSON files are supported."
      />,
    )
    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
    expect(screen.getByText('Unsupported file type')).toBeInTheDocument()
    expect(
      screen.getByText('Only CSV, XLSX, XLS, and JSON files are supported.'),
    ).toBeInTheDocument()
  })

  it('shows the too-large title and message', () => {
    render(
      <UploadValidationAlert
        error="too_large"
        message="File exceeds the 200 MB limit."
      />,
    )
    expect(screen.getByText('File too large')).toBeInTheDocument()
    expect(screen.getByText('File exceeds the 200 MB limit.')).toBeInTheDocument()
  })

  it('calls onDismiss when the dismiss button is clicked', () => {
    const onDismiss = vi.fn()
    render(
      <UploadValidationAlert
        error="unsupported"
        message="nope"
        onDismiss={onDismiss}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss error' }))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('does not render a dismiss button when onDismiss is omitted', () => {
    render(<UploadValidationAlert error="unsupported" message="nope" />)
    expect(
      screen.queryByRole('button', { name: 'Dismiss error' }),
    ).not.toBeInTheDocument()
  })
})