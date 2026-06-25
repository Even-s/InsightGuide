interface AnimatedStrikeTextProps {
  text: string
  done: boolean
  className: string
}

export default function AnimatedStrikeText({
  text,
  done,
  className,
}: AnimatedStrikeTextProps) {
  return (
    <span className={`relative inline-block max-w-full ${className}`}>
      <span className="transition-opacity duration-500 ease-out">{text}</span>
      <span
        className={`pointer-events-none absolute left-0 right-0 top-1/2 h-px origin-left -translate-y-1/2 bg-current transition-transform duration-500 ease-out ${done ? 'scale-x-100' : 'scale-x-0'}`}
        aria-hidden="true"
      />
    </span>
  )
}
