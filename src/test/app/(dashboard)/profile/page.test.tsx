import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import ProfilePage from '../../../../app/(dashboard)/profile/page'
import {
  avatarUrl,
  removeProfilePicture,
  updateProfileName,
  updateProfilePicture,
} from '../../../../lib/api'
import { useAuthStore } from '../../../../stores/auth-store'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('../../../../lib/api', () => ({
  avatarUrl: vi.fn((picture?: string | null) => picture ?? undefined),
  updateProfilePicture: vi.fn(),
  removeProfilePicture: vi.fn(),
  updateProfileName: vi.fn(),
}))

const toast = (await import('sonner')).toast as unknown as {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
}

const mockAvatarUrl = vi.mocked(avatarUrl)
const mockUpdateProfilePicture = vi.mocked(updateProfilePicture)
const mockRemoveProfilePicture = vi.mocked(removeProfilePicture)
const mockUpdateProfileName = vi.mocked(updateProfileName)

function selectImage(name = 'photo.jpg', type = 'image/jpeg'): File {
  const file = new File(['x'], name, { type })
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [file] } })
  return file
}

describe('ProfilePage', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 'u1', name: 'Alice', email: 'a@b.com' },
      isLoaded: true,
    })
    toast.success.mockClear()
    toast.error.mockClear()
    mockUpdateProfilePicture.mockReset()
    mockUpdateProfilePicture.mockResolvedValue({
      id: 'u1',
      name: 'Alice',
      email: 'a@b.com',
      picture: '/profiles/u1-1.jpg',
    })
    mockRemoveProfilePicture.mockReset()
    mockRemoveProfilePicture.mockResolvedValue({
      id: 'u1',
      name: 'Alice',
      email: 'a@b.com',
      picture: null,
    })
    mockAvatarUrl.mockReset()
    mockAvatarUrl.mockImplementation(
      (picture?: string | null) => picture ?? undefined,
    )
    mockUpdateProfileName.mockReset()
    mockUpdateProfileName.mockResolvedValue({
      id: 'u1',
      name: 'Alice Smith',
      email: 'a@b.com',
      picture: null,
    })
    URL.createObjectURL = vi.fn(() => 'blob:avatar-preview')
    URL.revokeObjectURL = vi.fn()
  })

  it('renders the heading and current account details', () => {
    render(<ProfilePage />)
    expect(screen.getByRole('heading', { name: 'Profile' })).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toHaveValue('Alice')
    expect(screen.getByLabelText('Email')).toHaveValue('a@b.com')
    expect(screen.getByLabelText('Email')).toHaveAttribute('readOnly')
  })

  it('renders nothing when there is no user', () => {
    useAuthStore.setState({ user: null })
    const { container } = render(<ProfilePage />)
    expect(container.innerHTML).toBe('')
  })

  it('shows the avatar initial when no picture is available', () => {
    render(<ProfilePage />)
    expect(screen.getByText('A')).toBeInTheDocument()
  })

  it('renders the avatar image when a picture is available', () => {
    useAuthStore.setState({
      user: {
        id: 'u1',
        name: 'Alice',
        email: 'a@b.com',
        picture: 'https://example.com/avatar.png',
      },
      isLoaded: true,
    })
    render(<ProfilePage />)
    expect(screen.getByAltText('Alice')).toHaveAttribute(
      'src',
      'https://example.com/avatar.png',
    )
  })

  it('offers a Change photo button and a JPG/PNG file input', () => {
    render(<ProfilePage />)
    expect(
      screen.getByRole('button', { name: /Change photo/ }),
    ).toBeInTheDocument()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.getAttribute('accept')).toContain('.jpg')
    expect(input.getAttribute('accept')).toContain('.jpeg')
    expect(input.getAttribute('accept')).toContain('.png')
  })

  it('rejects unsupported image types with an error toast', () => {
    render(<ProfilePage />)
    selectImage('photo.txt', 'text/plain')
    expect(toast.error).toHaveBeenCalledWith('Unsupported image', {
      description: 'Please choose a JPG, JPEG, or PNG image.',
    })
  })

  it('rejects images over the size limit with an error toast', () => {
    render(<ProfilePage />)
    const oversized = new File(
      [new ArrayBuffer(2 * 1024 * 1024 + 1)],
      'photo.jpg',
      { type: 'image/jpeg' },
    )
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [oversized] } })
    expect(toast.error).toHaveBeenCalledWith('Image too large', {
      description: 'Please choose an image under 2 MB.',
    })
  })

  it('previews a valid image and uploads it to the backend on save', async () => {
    render(<ProfilePage />)
    const file = selectImage('photo.jpg', 'image/jpeg')

    await waitFor(() => {
      expect(screen.getByAltText('Profile photo preview')).toHaveAttribute(
        'src',
        'blob:avatar-preview',
      )
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save photo' }))

    await waitFor(() => {
      expect(mockUpdateProfilePicture).toHaveBeenCalledWith(file)
      expect(useAuthStore.getState().user?.picture).toBe('/profiles/u1-1.jpg')
      expect(toast.success).toHaveBeenCalledWith('Photo updated', {
        description: 'Your profile photo was updated.',
      })
    })

    // Preview is replaced by the persisted picture.
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:avatar-preview')
    expect(screen.getByAltText('Alice')).toHaveAttribute(
      'src',
      '/profiles/u1-1.jpg',
    )
  })

  it('keeps the previous picture and toasts an error when saving the photo fails', async () => {
    mockUpdateProfilePicture.mockRejectedValueOnce(new Error('boom'))
    useAuthStore.setState({
      user: {
        id: 'u1',
        name: 'Alice',
        email: 'a@b.com',
        picture: 'https://example.com/avatar.png',
      },
      isLoaded: true,
    })
    render(<ProfilePage />)
    selectImage('photo.jpg', 'image/jpeg')

    await waitFor(() => {
      expect(screen.getByAltText('Profile photo preview')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save photo' }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to update photo', {
        description: 'Please try again.',
      })
    })
    expect(useAuthStore.getState().user?.picture).toBe(
      'https://example.com/avatar.png',
    )
  })

  it('does not offer removing the photo when there is no picture', () => {
    render(<ProfilePage />)
    expect(
      screen.queryByRole('button', { name: 'Remove photo' }),
    ).not.toBeInTheDocument()
  })

  it('removes the saved photo and restores the fallback initial when Remove photo is clicked', async () => {
    useAuthStore.setState({
      user: {
        id: 'u1',
        name: 'Alice',
        email: 'a@b.com',
        picture: 'https://example.com/avatar.png',
      },
      isLoaded: true,
    })
    render(<ProfilePage />)

    fireEvent.click(screen.getByRole('button', { name: 'Remove photo' }))

    await waitFor(() => {
      expect(mockRemoveProfilePicture).toHaveBeenCalledOnce()
      expect(useAuthStore.getState().user?.picture).toBeUndefined()
    })
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(toast.success).toHaveBeenCalledWith('Photo removed', {
      description: 'Your profile photo was removed.',
    })
  })

  it('keeps the picture and toasts an error when removing the photo fails', async () => {
    mockRemoveProfilePicture.mockRejectedValueOnce(new Error('boom'))
    useAuthStore.setState({
      user: {
        id: 'u1',
        name: 'Alice',
        email: 'a@b.com',
        picture: 'https://example.com/avatar.png',
      },
      isLoaded: true,
    })
    render(<ProfilePage />)

    fireEvent.click(screen.getByRole('button', { name: 'Remove photo' }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to remove photo', {
        description: 'Please try again.',
      })
    })
    expect(useAuthStore.getState().user?.picture).toBe(
      'https://example.com/avatar.png',
    )
  })

  it('cancels a pending photo selection and keeps the previous picture', async () => {
    useAuthStore.setState({
      user: {
        id: 'u1',
        name: 'Alice',
        email: 'a@b.com',
        picture: 'https://example.com/avatar.png',
      },
      isLoaded: true,
    })
    render(<ProfilePage />)
    selectImage('photo.jpg', 'image/jpeg')

    await waitFor(() => {
      expect(screen.getByAltText('Profile photo preview')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:avatar-preview')
    expect(screen.getByAltText('Alice')).toHaveAttribute(
      'src',
      'https://example.com/avatar.png',
    )
    expect(useAuthStore.getState().user?.picture).toBe(
      'https://example.com/avatar.png',
    )
  })

  it('disables saving until the name actually changes', () => {
    render(<ProfilePage />)
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Alice Smith' },
    })
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()

    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: '   ' },
    })
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('persists the new name through the backend and toasts on save', async () => {
    render(<ProfilePage />)
    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: '  Alice Smith  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(mockUpdateProfileName).toHaveBeenCalledWith('Alice Smith')
      expect(useAuthStore.getState().user?.name).toBe('Alice Smith')
      expect(toast.success).toHaveBeenCalledWith('Profile updated', {
        description: 'Your name was updated successfully.',
      })
    })
  })

  it('keeps the draft name and toasts an error when saving the name fails', async () => {
    mockUpdateProfileName.mockRejectedValueOnce(new Error('boom'))
    render(<ProfilePage />)
    fireEvent.change(screen.getByLabelText('Name'), {
      target: { value: 'Alice Smith' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to update name', {
        description: 'Please try again.',
      })
    })
    // Store keeps the old server value; input keeps the draft the user typed.
    expect(useAuthStore.getState().user?.name).toBe('Alice')
    expect(screen.getByLabelText('Name')).toHaveValue('Alice Smith')
  })
})