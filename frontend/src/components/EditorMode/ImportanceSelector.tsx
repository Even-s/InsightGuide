import type { CardImportance } from '@/types/questionCard'

interface ImportanceSelectorProps {
  value: CardImportance
  onChange: (value: CardImportance) => void
}

const options: Array<{ value: CardImportance; label: string; tone: string }> = [
  { value: 'must', label: '必講', tone: 'border-red-300 bg-red-50 text-red-700' },
  { value: 'should', label: '選講', tone: 'border-blue-300 bg-blue-50 text-blue-700' },
]

export default function ImportanceSelector({ value, onChange }: ImportanceSelectorProps) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded border px-3 py-2 text-sm font-medium transition-colors ${
            value === option.value ? option.tone : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
