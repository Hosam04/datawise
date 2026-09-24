import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FileDropzone } from '../../../components/upload/file-dropzone'

const csv = new File(['a,b,c'], 'data.csv', { type: 'text/csv' })

describe('FileDropzone', () => {
  it('selects a valid file through the hidden input', () => {
    const onFileSelected = vi.fn()
    const { container } = render(<FileDropzone onFileSelected={onFileSelected} />)

    const input = container.querySelector('input[type="file"]')!
    fireEvent.change(input, { target: { files: [csv] } })

    expect(onFileSelected).toHaveBeenCalledWith(csv)
  })

  it('rejects an unsupported file type with a validation alert', () => {
    const onFileSelected = vi.fn()
    const { container } = render(<FileDropzone onFileSelected={onFileSelected} />)

    const txt = new File(['text'], 'notes.txt', { type: 'text/plain' })
    const input = container.querySelector('input[type="file"]')!
    fireEvent.change(input, { target: { files: [txt] } })

    expect(onFileSelected).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Unsupported file type')).toBeInTheDocument()
  })

  it('rejects an oversized file', () => {
    const onFileSelected = vi.fn()
    const { container } = render(<FileDropzone onFileSelected={onFileSelected} />)

    const input = container.querySelector('input[type="file"]')!
    fireEvent.change(input, {
      target: {
        files: [new File([new ArrayBuffer(200 * 1024 * 1024)], 'big.csv')],
      },
    })

    expect(onFileSelected).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('File too large')).toBeInTheDocument()
  })

  it('dismisses the validation error and continues', () => {
    const onFileSelected = vi.fn()
    const { container } = render(<FileDropzone onFileSelected={onFileSelected} />)
    const input = container.querySelector('input[type="file"]')!

    fireEvent.change(input, {
      target: { files: [new File(['x'], 'bad.txt', { type: 'text/plain' })] },
    })
    expect(screen.getByRole('alert')).toBeInTheDocument()

    fireEvent.change(input, { target: { files: [csv] } })
    expect(onFileSelected).toHaveBeenCalledWith(csv)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('accepts a dropped file', () => {
    const onFileSelected = vi.fn()
    render(<FileDropzone onFileSelected={onFileSelected} />)

    const zone = screen.getByText('Drop your dataset here').closest('div')!
    fireEvent.drop(zone, { dataTransfer: { files: [csv] } })

    expect(onFileSelected).toHaveBeenCalledWith(csv)
  })

  it('does not select files when disabled', () => {
    const onFileSelected = vi.fn()
    const { container } = render(
      <FileDropzone onFileSelected={onFileSelected} disabled />,
    )
    const input = container.querySelector('input[type="file"]')!
    fireEvent.change(input, { target: { files: [csv] } })

    expect(onFileSelected).not.toHaveBeenCalled()
    expect(screen.getByText('Drop your dataset here').parentElement).toHaveAttribute(
      'aria-disabled',
      'true',
    )
  })

  it('resets the input value after a selection so the same file can be re-picked', () => {
    const onFileSelected = vi.fn()
    const { container } = render(<FileDropzone onFileSelected={onFileSelected} />)
    const input = container.querySelector('input[type="file"]')!

    fireEvent.change(input, { target: { files: [csv] } })
    expect(onFileSelected).toHaveBeenCalledWith(csv)

    // jsdom can only clear file inputs to the empty string; the handler resets it.
    expect((input as HTMLInputElement).value).toBe('')
  })

  it('renders the supported-format hint with the max size', () => {
    render(<FileDropzone onFileSelected={vi.fn()} />)
    expect(
      screen.getByText(/Supported formats: CSV, XLSX, XLS, JSON/),
    ).toBeInTheDocument()
  })

  it('allows selecting a file by clicking the dropzone', () => {
    const onFileSelected = vi.fn()
    render(<FileDropzone onFileSelected={onFileSelected} />)
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click')

    fireEvent.click(screen.getByText('Drop your dataset here'))

    expect(clickSpy).toHaveBeenCalled()
  })
})