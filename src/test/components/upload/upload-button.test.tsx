import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UploadButton } from '../../../components/upload/upload-button'

describe('UploadButton', () => {
  it('renders the label and fires onUpload', () => {
    const onUpload = vi.fn()
    render(<UploadButton onUpload={onUpload} />)
    const button = screen.getByRole('button', { name: 'Start Analysis' })
    fireEvent.click(button)
    expect(onUpload).toHaveBeenCalledTimes(1)
  })

  it('is disabled when asked and does not fire onUpload', () => {
    const onUpload = vi.fn()
    render(<UploadButton disabled onUpload={onUpload} />)
    const button = screen.getByRole('button', { name: 'Start Analysis' })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(onUpload).not.toHaveBeenCalled()
  })
})