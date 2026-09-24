'use client'

import { useEffect, useRef, useState, type ReactElement, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ConfirmDialogProps {
  trigger: ReactNode
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  tooltip?: string
  disabled?: boolean
  onConfirm: () => void
}

function ConfirmDialogTrigger({
  tooltip,
  trigger,
}: {
  tooltip?: string
  trigger: ReactNode
}) {
  if (!tooltip) {
    return <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
  }

  return (
    <BaseTooltip.Root>
      <BaseTooltip.Trigger
        render={
          <Dialog.Trigger asChild>{trigger as ReactElement}</Dialog.Trigger>
        }
      />
      <BaseTooltip.Portal>
        <BaseTooltip.Positioner side="top" sideOffset={6}>
          <BaseTooltip.Popup
            className={cn(
              'z-50 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-foreground shadow-md',
              'origin-(--transform-origin)',
              'transition-[transform,opacity] duration-150 ease-out',
              'data-starting-style:scale-95 data-starting-style:opacity-0',
              'data-ending-style:scale-95 data-ending-style:opacity-0',
              'data-instant:transition-none',
            )}
          >
            {tooltip}
          </BaseTooltip.Popup>
        </BaseTooltip.Positioner>
      </BaseTooltip.Portal>
    </BaseTooltip.Root>
  )
}

export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  tooltip,
  disabled = false,
  onConfirm,
}: ConfirmDialogProps) {
  const [open, setOpen] = useState(false)
  const pendingConfirmRef = useRef(false)
  const onConfirmRef = useRef(onConfirm)

  useEffect(() => {
    onConfirmRef.current = onConfirm
  }, [onConfirm])

  useEffect(() => {
    if (open || !pendingConfirmRef.current) return

    pendingConfirmRef.current = false
    onConfirmRef.current()
  }, [open])

  const handleConfirm = () => {
    pendingConfirmRef.current = true
    setOpen(false)
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (disabled && newOpen) {
      return
    }
    setOpen(newOpen)
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <ConfirmDialogTrigger tooltip={tooltip} trigger={trigger} />

      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 z-50 bg-black/50',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
          )}
        />

        <Dialog.Content
          onEscapeKeyDown={() => setOpen(false)}
          className={cn(
            'fixed top-1/2 left-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2',
            'rounded-xl border border-border bg-card p-6 shadow-lg',
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
          )}
        >
          <Dialog.Title className="text-lg font-semibold text-foreground">
            {title}
          </Dialog.Title>

          <Dialog.Description className="mt-2 text-sm text-muted-foreground">
            {description}
          </Dialog.Description>

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="outline">{cancelLabel}</Button>
            </Dialog.Close>

            <Button variant="destructive" onClick={handleConfirm}>
              {confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
