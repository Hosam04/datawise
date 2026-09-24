'use client'

import * as React from 'react'
import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip'
import { cn } from '@/lib/utils'

const tooltipPopupClassName = cn(
  'z-50 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-foreground shadow-md',
  'origin-(--transform-origin)',
  'transition-[transform,opacity] duration-150 ease-out',
  'data-starting-style:scale-95 data-starting-style:opacity-0',
  'data-ending-style:scale-95 data-ending-style:opacity-0',
  'data-instant:transition-none',
)

export function TooltipProvider({
  children,
  delay = 400,
}: {
  children: React.ReactNode
  delay?: number
}) {
  return <BaseTooltip.Provider delay={delay}>{children}</BaseTooltip.Provider>
}

interface TooltipProps {
  content: string
  children: React.ReactElement
  side?: 'top' | 'bottom' | 'left' | 'right'
  sideOffset?: number
  disabled?: boolean
}

export function Tooltip({
  content,
  children,
  side = 'bottom',
  sideOffset = 6,
  disabled = false,
}: TooltipProps) {
  if (disabled) {
    return children
  }

  return (
    <BaseTooltip.Root>
      <BaseTooltip.Trigger render={children} />
      <BaseTooltip.Portal>
        <BaseTooltip.Positioner side={side} sideOffset={sideOffset}>
          <BaseTooltip.Popup className={tooltipPopupClassName}>
            {content}
          </BaseTooltip.Popup>
        </BaseTooltip.Positioner>
      </BaseTooltip.Portal>
    </BaseTooltip.Root>
  )
}

interface IconTooltipProps
  extends Omit<TooltipProps, 'children' | 'content'>,
    Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  label: string
  children: React.ReactNode
}

export function IconTooltip({
  label,
  children,
  className,
  disabled,
  onClick,
  type = 'button',
  side,
  sideOffset,
  ...buttonProps
}: IconTooltipProps) {
  return (
    <Tooltip
      content={label}
      side={side}
      sideOffset={sideOffset}
      disabled={disabled}
    >
      <button
        type={type}
        aria-label={label}
        disabled={disabled}
        onClick={onClick}
        className={className}
        {...buttonProps}
      >
        {children}
      </button>
    </Tooltip>
  )
}
