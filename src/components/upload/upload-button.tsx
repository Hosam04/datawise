'use client'

import { Upload } from 'lucide-react'

interface UploadButtonProps {
  disabled?: boolean
  onUpload?: () => void
}

export function UploadButton({
  disabled = false,
  onUpload,
}: UploadButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onUpload}
      className="
        flex items-center justify-center gap-2
        rounded-xl
        bg-primary
        px-6
        py-3
        text-sm
        font-medium
        text-primary-foreground
        transition
        hover:bg-primary/90
        disabled:pointer-events-none
        disabled:opacity-50
      "
    >
      <Upload className="size-4" />

      Start Analysis
    </button>
  )
}