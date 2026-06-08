import { Skeleton } from './Skeleton'
import { useStats } from '../api/hooks'
import './Stats.css'

// Fallback shown while loading or when API fails
const FALLBACK_STATS = [
  { value: '4 500+', label: 'Proizvoda',            icon: '📦' },
  { value: '5',      label: 'Web-dućana',            icon: '🏪' },
  { value: '11',     label: 'Kategorija',            icon: '📂' },
  { value: '€0',     label: 'Naknada za korištenje', icon: '🎁' },
]

/** Format e.g. 4573 → "4 573+" using non-breaking space as thousands separator. */
function formatCount(n: number): string {
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0') + '+'
}

export default function Stats() {
  const { data, isLoading } = useStats()
  const s = data?.data

  // Falls back to hardcoded values on error (s is undefined when fetch fails)
  const stats = s
    ? [
        { value: formatCount(s.products_total), label: 'Proizvoda',            icon: '📦' },
        { value: String(s.stores_total),         label: 'Web-dućana',            icon: '🏪' },
        { value: String(s.categories_total),     label: 'Kategorija',            icon: '📂' },
        { value: '€0',                           label: 'Naknada za korištenje', icon: '🎁' },
      ]
    : FALLBACK_STATS

  return (
    <section className="stats" aria-label="Statistike">
      <div className="container">
        <ul className="stats__grid">
          {stats.map((stat) => (
            <li key={stat.label} className="stats__item">
              <span className="stats__icon" aria-hidden="true">{stat.icon}</span>
              {isLoading ? (
                <Skeleton className="stats__skeleton" />
              ) : (
                <span className="stats__value">{stat.value}</span>
              )}
              <span className="stats__label">{stat.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
