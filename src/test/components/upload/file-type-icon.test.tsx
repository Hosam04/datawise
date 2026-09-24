import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FileTypeIcon } from '../../../components/upload/file-type-icon'

describe('FileTypeIcon', () => {
  it('labels the CSV kind', () => {
    render(<FileTypeIcon kind="csv" showLabel />)
    expect(screen.getByText('CSV')).toBeInTheDocument()
  })

  it('labels the Excel kind', () => {
    render(<FileTypeIcon kind="excel" showLabel />)
    expect(screen.getByText('Excel')).toBeInTheDocument()
  })

  it('labels the JSON kind', () => {
    render(<FileTypeIcon kind="json" showLabel />)
    expect(screen.getByText('JSON')).toBeInTheDocument()
  })

  it('renders the icon without a label by default', () => {
    render(<FileTypeIcon kind="json" />)
    expect(screen.queryByText('JSON')).not.toBeInTheDocument()
  })
})