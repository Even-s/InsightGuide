interface LoadingSpinnerProps {
  label?: string
}

export default function LoadingSpinner({ label = '載入中...' }: LoadingSpinnerProps) {
  return (
    <div className="flex h-full min-h-48 items-center justify-center">
      <div className="text-center">
        <div className="mx-auto mb-3 h-10 w-10 animate-spin rounded-full border-2 border-cream-200 border-t-sage-400" />
        <p className="text-sm text-natural-600">{label}</p>
      </div>
    </div>
  )
}
