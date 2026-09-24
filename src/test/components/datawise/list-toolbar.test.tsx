import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ListSearch, ListFilter, ListSort, ListToolbar } from '../../../components/datawise/list-toolbar'

describe('ListSearch', () => {
  it('renders with the custom placeholder and reports changes', () => {
    const onChange = vi.fn()
    render(<ListSearch value="" onChange={onChange} placeholder="Find stuff" />)
    const input = screen.getByPlaceholderText('Find stuff')
    fireEvent.change(input, { target: { value: 'abc' } })
    expect(onChange).toHaveBeenCalledWith('abc')
  })
})

describe('ListFilter', () => {
  it('marks the active option and switches on click', () => {
    const onChange = vi.fn()
    render(
      <ListFilter
        value="pending"
        onChange={onChange}
        options={[
          { value: 'all', label: 'All' },
          { value: 'pending', label: 'Pending' },
        ]}
      />,
    )
    expect(screen.getByRole('button', { name: 'Pending' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    expect(onChange).toHaveBeenCalledWith('all')
  })
})

describe('ListSort', () => {
  it('renders the options and reports a selection', () => {
    const onChange = vi.fn()
    render(
      <ListSort
        value="date-desc"
        onChange={onChange}
        options={[
          { value: 'date-desc', label: 'Newest' },
          { value: 'title-asc', label: 'A-Z' },
        ]}
      />,
    )
    const select = screen.getByRole('combobox')
    expect(select).toHaveValue('date-desc')
    fireEvent.change(select, { target: { value: 'title-asc' } })
    expect(onChange).toHaveBeenCalledWith('title-asc')
  })
})

describe('ListToolbar', () => {
  it('renders nothing when no widgets are enabled', () => {
    const { container } = render(<ListToolbar />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders search, filter, and sort together', () => {
    const search = vi.fn()
    const filter = vi.fn()
    const sort = vi.fn()
    render(
      <ListToolbar
        search=""
        onSearchChange={search}
        searchPlaceholder="Search datasets"
        filter="all"
        onFilterChange={filter}
        filterOptions={[{ value: 'all', label: 'All' }]}
        sort="date-desc"
        onSortChange={sort}
        sortOptions={[{ value: 'date-desc', label: 'Newest' }]}
      />,
    )
    expect(screen.getByPlaceholderText('Search datasets')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toHaveValue('date-desc')
  })
})