import { authFetch, API_URL, assetUrl, errorMessage } from '@/lib/api'
import type { ProfileUser } from '@/lib/api'

export async function fetchMe(): Promise<ProfileUser> {
  const response = await authFetch(`${API_URL}/auth/me`)
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to load profile'))
  }
  return (await response.json()) as ProfileUser
}

export async function updateProfileName(name: string): Promise<ProfileUser> {
  const response = await authFetch(`${API_URL}/auth/me`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to update profile'))
  }
  return (await response.json()) as ProfileUser
}

export async function updateProfilePicture(file: File): Promise<ProfileUser> {
  const form = new FormData()
  form.append('file', file, file.name)
  const response = await authFetch(`${API_URL}/auth/me/picture`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Failed to update profile photo'))
  }
  return (await response.json()) as ProfileUser
}

export async function removeProfilePicture(): Promise<ProfileUser> {
  const response = await authFetch(`${API_URL}/auth/me/picture`, {
    method: 'DELETE',
  })
  if (!response.ok && response.status !== 404) {
    throw new Error(await errorMessage(response, 'Failed to remove profile photo'))
  }
  return (await response.json()) as ProfileUser
}

export function avatarUrl(picture?: string | null): string | undefined {
  if (!picture) return undefined
  if (picture.startsWith('http') || picture.startsWith('data:')) return picture
  return assetUrl(picture)
}

export type { ProfileUser }