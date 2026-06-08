import './EmptyState.css'

interface EmptyStateProps {
  title?: string
  description?: string
}

export default function EmptyState({
  title = 'Nema rezultata',
  description = 'Pokušaj s drugačijim filterima ili pojmom pretrage.',
}: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon" aria-hidden="true">🔍</div>
      <h3 className="empty-state__title">{title}</h3>
      <p className="empty-state__desc">{description}</p>
    </div>
  )
}
