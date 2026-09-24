import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DetailSection, MetadataGrid, ActionBar } from '../../../components/datawise/detail-section'

describe('DetailSection', () => {
  it('renders title, optional description, and children', () => {
    render(
      <DetailSection title="Overview" description="Key information">
        <p>content</p>
      </DetailSection>,
    )
    expect(
      screen.getByRole('heading', { name: 'Overview' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Key information')).toBeInTheDocument()
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('omits the description when not provided', () => {
    render(<DetailSection title="Overview">x</DetailSection>)
    expect(screen.queryByText(/Key information/)).not.toBeInTheDocument()
  })
})

describe('MetadataGrid', () => {
  it('renders label/value pairs as a definition list', () => {
    const items = [
      { label: 'Rows', value: '1200' },
      { label: 'Columns', value: '42' },
    ]
    render(<MetadataGrid items={items} />)
    expect(screen.getByText('Rows')).toBeInTheDocument()
    expect(screen.getByText('1200')).toBeInTheDocument()
    expect(screen.getByText('Columns')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })
})

describe('ActionBar', () => {
  it('renders its children', () => {
    render(<ActionBar>some actions</ActionBar>)
    expect(screen.getByText('some actions')).toBeInTheDocument()
  })
})