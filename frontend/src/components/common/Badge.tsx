import clsx from 'clsx'
import type { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
  tone?: 'gray' | 'blue' | 'green' | 'yellow' | 'red'
  size?: 'sm' | 'md'
  className?: string
}

const tones = {
  gray: 'bg-cream-200 text-natural-700',
  blue: 'bg-sage-100 text-sage-600',
  green: 'bg-sage-200 text-sage-700',
  yellow: 'bg-wood-100 text-wood-600',
  red: 'bg-wood-200 text-wood-600',
}

const sizes = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-0.5 text-xs',
}

export default function Badge({ children, tone = 'gray', size = 'md', className }: BadgeProps) {
  return (
    <span className={clsx('inline-flex items-center rounded-lg font-medium tracking-wide', tones[tone], sizes[size], className)}>
      {children}
    </span>
  )
}
