import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { UploadProgress } from '../../../components/upload/upload-progress'

describe('UploadProgress', () => {
  it('shows upload state with a clamped progress bar but the raw percentage', () => {
    render(
      <UploadProgress progress={150} status="uploading" fileName="a.csv" />,
    )
    expect(screen.getByText('Uploading Dataset...')).toBeInTheDocument()
    expect(screen.getByText('150%')).toBeInTheDocument()
    expect(screen.getByText('a.csv')).toBeInTheDocument()
  })

  it('floors progress at zero for the bar width', () => {
    const { container } = render(
      <UploadProgress progress={-5} status="uploading" />,
    )
    const bar = Array.from(container.querySelectorAll('div')).find(
      (el) => (el as HTMLElement).style.width === '0%',
    )
    expect(bar).toBeDefined()
  })

  it('shows the processing state without a numeric percentage', () => {
    render(<UploadProgress progress={40} status="processing" fileName="a.csv" />)
    expect(screen.getByText('Processing Dataset...')).toBeInTheDocument()
    expect(screen.getByText('Analyzing')).toBeInTheDocument()
    expect(screen.getByText('AI agents are analyzing your data...')).toBeInTheDocument()
    expect(screen.queryByText('40%')).not.toBeInTheDocument()
  })

  it('shows the completed state at 100%', () => {
    render(<UploadProgress progress={100} status="completed" fileName="b.csv" />)
    expect(screen.getByText('Analysis Complete')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(screen.getByText('b.csv is ready.')).toBeInTheDocument()
  })

  it('shows a generic ready message when completed without a file name', () => {
    render(<UploadProgress progress={100} status="completed" />)
    expect(screen.getByText('Your dataset is ready.')).toBeInTheDocument()
  })

  it('shows the error state with the error message', () => {
    render(
      <UploadProgress
        progress={40}
        status="error"
        fileName="a.csv"
        errorMessage="Backend down"
      />,
    )
    expect(screen.getByText('Analysis Failed')).toBeInTheDocument()
    expect(screen.getByText('Backend down')).toBeInTheDocument()
  })

  it('shows a generic error message when error state lacks one', () => {
    render(<UploadProgress progress={40} status="error" />)
    expect(screen.getByText('Something went wrong.')).toBeInTheDocument()
  })

  it('falls back for an idle status', () => {
    render(<UploadProgress progress={0} status="idle" />)
    expect(screen.getByText('Uploading Dataset...')).toBeInTheDocument()
    expect(screen.getByText('Sending file to server...')).toBeInTheDocument()
  })
})