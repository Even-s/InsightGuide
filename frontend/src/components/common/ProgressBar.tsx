interface ProgressBarProps {
  value: number
  max?: number
  tone?: 'blue' | 'green' | 'yellow' | 'red'
}

const toneClasses = {
  blue: 'bg-sage-400',
  green: 'bg-sage-400',
  yellow: 'bg-wood-300',
  red: 'bg-wood-400',
}

export default function ProgressBar({ value, max = 100, tone = 'blue' }: ProgressBarProps) {
  const percentage = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0

  return (
    <div className="h-2 overflow-hidden rounded-full bg-cream-200">
      <div
        className={`h-full transition-all duration-500 ${toneClasses[tone]}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}
