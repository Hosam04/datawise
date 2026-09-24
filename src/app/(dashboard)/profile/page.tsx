'use client'

import { useRef, useState } from 'react'
import { Camera, Loader2, Save, Trash2, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { avatarUrl, removeProfilePicture, updateProfileName, updateProfilePicture } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth-store'

const ALLOWED_PROFILE_PICTURE_TYPES = ['image/jpeg', 'image/png']
const ALLOWED_PROFILE_PICTURE_EXTENSIONS = ['.jpg', '.jpeg', '.png']
const MAX_PROFILE_PICTURE_BYTES = 2 * 1024 * 1024
const MAX_PROFILE_PICTURE_MB = 2

function ProfileSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </section>
  )
}

export default function ProfilePage() {
  const { user, setUser } = useAuthStore()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [draftName, setDraftName] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [draftFile, setDraftFile] = useState<File | null>(null)
  const [draftPreview, setDraftPreview] = useState<string | null>(null)
  const [photoSaving, setPhotoSaving] = useState(false)
  const [photoRemoving, setPhotoRemoving] = useState(false)

  if (!user) return null

  const currentName = user.name ?? ''
  const name = draftName ?? currentName
  const initial = currentName.trim()[0]?.toUpperCase() ?? 'D'
  const trimmedName = name.trim()
  const canSave = trimmedName.length > 0 && trimmedName !== currentName
  const avatarSource = draftPreview ?? avatarUrl(user.picture)

  const handleSaveName = async () => {
    if (!canSave) return

    setSaving(true)
    try {
      const updated = await updateProfileName(trimmedName)
      setUser({
        ...user,
        name: updated.name,
        picture: updated.picture ?? undefined,
      })
      setDraftName(null)
      toast.success('Profile updated', {
        description: 'Your name was updated successfully.',
      })
    } catch {
      toast.error('Failed to update name', {
        description: 'Please try again.',
      })
    } finally {
      setSaving(false)
    }
  }

  const openFilePicker = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    const allowedType =
      ALLOWED_PROFILE_PICTURE_TYPES.includes(file.type) &&
      ALLOWED_PROFILE_PICTURE_EXTENSIONS.includes(extension)

    if (!allowedType) {
      toast.error('Unsupported image', {
        description: 'Please choose a JPG, JPEG, or PNG image.',
      })
      return
    }

    if (file.size > MAX_PROFILE_PICTURE_BYTES) {
      toast.error('Image too large', {
        description: `Please choose an image under ${MAX_PROFILE_PICTURE_MB} MB.`,
      })
      return
    }

    // Preview via an object URL — the raw file is never turned into base64 or
    // written to Zustand/localStorage. It is only uploaded when the user saves.
    if (draftPreview) {
      URL.revokeObjectURL(draftPreview)
    }
    setDraftFile(file)
    setDraftPreview(URL.createObjectURL(file))
  }

  const handleSavePhoto = async () => {
    if (!draftFile) return

    setPhotoSaving(true)
    try {
      const updated = await updateProfilePicture(draftFile)
      setUser({
        ...user,
        picture: updated.picture ?? undefined,
      })
      if (draftPreview) {
        URL.revokeObjectURL(draftPreview)
      }
      setDraftFile(null)
      setDraftPreview(null)
      toast.success('Photo updated', {
        description: 'Your profile photo was updated.',
      })
    } catch {
      toast.error('Failed to update photo', {
        description: 'Please try again.',
      })
    } finally {
      setPhotoSaving(false)
    }
  }

  const handleRemovePhoto = async () => {
    if (!user.picture) return

    setPhotoRemoving(true)
    try {
      const updated = await removeProfilePicture()
      setUser({
        ...user,
        picture: updated.picture ?? undefined,
      })
      toast.success('Photo removed', {
        description: 'Your profile photo was removed.',
      })
    } catch {
      toast.error('Failed to remove photo', {
        description: 'Please try again.',
      })
    } finally {
      setPhotoRemoving(false)
    }
  }

  const handleCancelPhoto = () => {
    if (draftPreview) {
      URL.revokeObjectURL(draftPreview)
    }
    setDraftFile(null)
    setDraftPreview(null)
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">Profile</h1>
        <p className="mt-2 text-muted-foreground">
          View and manage your account information.
        </p>
      </div>

      <ProfileSection
        title="Profile photo & name"
        description="This is how you appear across DataWise."
      >
        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex size-20 shrink-0 items-center justify-center overflow-hidden rounded-full bg-accent text-2xl font-semibold text-accent-foreground">
              {avatarSource ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={avatarSource}
                  alt={draftPreview ? 'Profile photo preview' : currentName}
                  className="h-full w-full object-cover"
                />
              ) : (
                initial
              )}
            </div>

            <div className="flex flex-col items-start gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={openFilePicker}
                >
                  <Camera className="size-4" aria-hidden="true" />
                  Change photo
                </Button>

                {user.picture && !draftFile && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={handleRemovePhoto}
                    disabled={photoRemoving}
                    className="text-destructive hover:text-destructive"
                  >
                    {photoRemoving ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Trash2 className="size-4" aria-hidden="true" />
                    )}
                    {photoRemoving ? 'Removing...' : 'Remove photo'}
                  </Button>
                )}

                {draftFile && (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      onClick={handleSavePhoto}
                      disabled={photoSaving}
                    >
                      {photoSaving ? (
                        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <Save className="size-4" aria-hidden="true" />
                      )}
                      {photoSaving ? 'Saving...' : 'Save photo'}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleCancelPhoto}
                    >
                      <X className="size-4" aria-hidden="true" />
                      Cancel
                    </Button>
                  </>
                )}
              </div>

              <p className="text-xs text-muted-foreground">
                JPG, JPEG, or PNG up to {MAX_PROFILE_PICTURE_MB} MB.
              </p>

              <input
                ref={fileInputRef}
                type="file"
                accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                className="sr-only"
                onChange={handleFileChange}
                aria-label="Choose a profile photo"
              />
            </div>
          </div>

          <div className="w-full space-y-3 sm:max-w-sm">
            <div className="space-y-2">
              <label
                htmlFor="profile-name"
                className="block text-sm font-medium text-foreground"
              >
                Name
              </label>
              <input
                id="profile-name"
                type="text"
                value={name}
                onChange={(event) => setDraftName(event.target.value)}
                maxLength={60}
                className={cn(
                  'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:ring-2 focus:ring-ring',
                )}
              />
            </div>

            <Button type="button" onClick={handleSaveName} disabled={!canSave || saving}>
              {saving ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="size-4" aria-hidden="true" />
              )}
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </ProfileSection>

      <ProfileSection
        title="Email"
        description="Your sign-in email address."
      >
        <div className="space-y-2">
          <label
            htmlFor="profile-email"
            className="block text-sm font-medium text-foreground"
          >
            Email
          </label>
          <input
            id="profile-email"
            type="email"
            value={user.email ?? ''}
            readOnly
            disabled
            className={cn(
              'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-70 sm:max-w-sm',
            )}
          />
          <p className="text-sm text-muted-foreground">
            Email cannot be changed here.
          </p>
        </div>
      </ProfileSection>
    </div>
  )
}