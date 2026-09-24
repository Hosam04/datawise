'use client'

import { UploadCloud } from 'lucide-react'
import { useRef, useState } from 'react'
import { UploadValidationAlert } from '@/components/upload/upload-validation-alert'
import {
  MAX_UPLOAD_SIZE_MB,
  validateUploadFile,
  type UploadValidationError,
} from '@/lib/upload-utils'
import { cn } from '@/lib/utils'

interface FileDropzoneProps {
  onFileSelected: (file: File) => void
  disabled?: boolean
}

export function FileDropzone({ onFileSelected, disabled = false }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [validationError, setValidationError] = useState<{
    error: UploadValidationError
    message: string
  } | null>(null)

  const handleFile = (file?: File) => {
    if (!file || disabled) return

    const result = validateUploadFile(file)

    if (!result.ok) {
      setValidationError({
        error: result.error,
        message: result.message,
      })
      return
    }

    setValidationError(null)
    onFileSelected(file)
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        onDragOver={(e) => {
          if (disabled) return
          e.preventDefault()
        }}
        onDrop={(e) => {
          if (disabled) return
          e.preventDefault()
          handleFile(e.dataTransfer.files[0])
        }}
        onClick={() => {
          if (disabled) return
          inputRef.current?.click()
        }}
        aria-disabled={disabled}
        className={cn(
          'flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-background p-10 transition',
          disabled
            ? 'cursor-not-allowed opacity-50'
            : 'cursor-pointer hover:bg-muted',
          validationError && !disabled && 'border-destructive/40',
        )}
      >
        <UploadCloud className="mb-4 size-12 text-primary" />

        <h2 className="text-lg font-semibold text-foreground">
          Drop your dataset here
        </h2>

        <p className="mt-2 text-sm text-muted-foreground">
          or click to browse files
        </p>

        <p className="mt-4 text-xs text-muted-foreground">
          Supported formats: CSV, XLSX, XLS, JSON · Max {MAX_UPLOAD_SIZE_MB} MB
        </p>

        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.json"
          hidden
          disabled={disabled}
          onChange={(e) => {
            handleFile(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>

      {validationError && (
        <UploadValidationAlert
          error={validationError.error}
          message={validationError.message}
          onDismiss={() => setValidationError(null)}
        />
      )}
    </div>
  )
}
