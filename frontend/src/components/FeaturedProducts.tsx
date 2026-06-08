import { Link } from 'react-router-dom'
import { useGroups } from '../api/hooks'
import ProductCard from './ProductCard'
import { ProductCardSkeleton } from './Skeleton'
import ErrorMessage from './ErrorMessage'
import './FeaturedProducts.css'

const LIMIT = 6

export default function FeaturedProducts() {
  // Top 6 groups sorted by largest savings (most compelling price comparisons first)
  const { data, isLoading, isError, refetch } = useGroups({ sortiraj: 'usteda_pad', limit: LIMIT })
  const groups = data?.data ?? []

  return (
    <section className="featured section" id="proizvodi">
      <div className="container">
        <header className="section-header">
          <div className="badge badge--gold" style={{ marginBottom: '1rem' }}>Istaknuto</div>
          <h2>Najpraćeniji proizvodi</h2>
          <p>Pogledaj gdje je danas najjeftinije kupiti najpopularnija pića.</p>
        </header>

        {isError ? (
          <ErrorMessage
            message="Nismo mogli učitati istaknute proizvode."
            onRetry={() => refetch()}
          />
        ) : (
          <div className="featured__grid">
            {isLoading
              ? Array.from({ length: LIMIT }).map((_, i) => <ProductCardSkeleton key={i} />)
              : groups.map((g) => <ProductCard key={g.group_id} group={g} />)
            }
          </div>
        )}

        <div className="featured__cta">
          <Link to="/pregled" className="btn btn--ghost">
            Vidi sve proizvode
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </div>
    </section>
  )
}
