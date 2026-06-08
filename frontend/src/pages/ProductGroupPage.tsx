import { useParams, Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import PriceComparisonTable from '../components/PriceComparisonTable'
import { Skeleton } from '../components/Skeleton'
import ErrorMessage from '../components/ErrorMessage'
import { useGroupDetail } from '../api/hooks'
import { getCategoryMeta } from '../api/categoryIcons'
import './ProductGroupPage.css'

function formatVolume(ml: number | null): string {
  if (!ml) return ''
  if (ml >= 1000 && ml % 1000 === 0) return `${ml / 1000} L`
  if (ml >= 1000) return `${(ml / 1000).toFixed(1)} L`
  return `${ml} ml`
}

export default function ProductGroupPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const groupId = `g${matchId ?? ''}`

  const { data, isLoading, isError, refetch } = useGroupDetail(groupId)
  const group = data?.data

  const meta = getCategoryMeta(group?.category_slug)

  const cheapestStore = group?.stores.find((s) => s.is_cheapest)

  // Pick hero image by reliability priority, not price order
  const IMAGE_PRIORITY = ['ecuga', 'cugaklik', 'diskontfumar', 'promili', 'rotodinamic']
  const displayImage = group
    ? (IMAGE_PRIORITY.map(name => group.stores.find(s => s.store_name === name)?.image_url ?? null)
        .find(url => url != null) ?? null)
    : null

  return (
    <>
      <Navbar />
      <main className="pgp">
        <div className="pgp__container container">
          {/* Breadcrumb */}
          <nav className="pgp__breadcrumb" aria-label="Navigacijska putanja">
            <Link to="/" className="pgp__crumb-link">Početna</Link>
            <span className="pgp__crumb-sep" aria-hidden="true">›</span>
            <Link to="/pregled" className="pgp__crumb-link">Pregled</Link>
            {group && (
              <>
                <span className="pgp__crumb-sep" aria-hidden="true">›</span>
                <Link
                  to={`/pregled?kategorija=${group.category_slug}`}
                  className="pgp__crumb-link"
                >
                  {group.category_name}
                </Link>
              </>
            )}
          </nav>

          {isError && (
            <ErrorMessage
              message="Nismo mogli učitati podatke o proizvodu. Pokušaj ponovo."
              onRetry={() => refetch()}
            />
          )}

          {isLoading && (
            <div className="pgp__layout">
              <div className="pgp__left">
                <Skeleton className="pgp__image-skeleton" />
                <Skeleton className="pgp__tag-skeleton" />
                <Skeleton className="pgp__tag-skeleton" />
              </div>
              <div className="pgp__right">
                <Skeleton className="pgp__title-skeleton" />
                <Skeleton className="pgp__subtitle-skeleton" />
                <Skeleton className="pgp__table-skeleton" />
              </div>
            </div>
          )}

          {!isLoading && !isError && group && (
            <div className="pgp__layout">
              {/* ─── Left column ─────────────────────────────────── */}
              <aside className="pgp__left">
                <div className="pgp__image-wrap">
                  {displayImage ? (
                    <img
                      src={displayImage}
                      alt={group.display_title}
                      className="pgp__image"
                      onError={(e) => {
                        const target = e.currentTarget
                        target.style.display = 'none'
                        const fallback = target.nextElementSibling as HTMLElement | null
                        if (fallback) fallback.style.display = 'flex'
                      }}
                    />
                  ) : null}
                  <div
                    className="pgp__image-fallback"
                    style={{
                      background: meta.gradient,
                      display: displayImage ? 'none' : 'flex',
                    }}
                  >
                    <span className="pgp__image-icon" aria-hidden="true">{meta.icon}</span>
                  </div>
                </div>

                {/* Tags */}
                <div className="pgp__tags">
                  <span className="pgp__tag pgp__tag--category">
                    {meta.icon} {group.category_name}
                  </span>
                  {group.volume_ml && (
                    <span className="pgp__tag pgp__tag--volume">
                      {formatVolume(group.volume_ml)}
                    </span>
                  )}
                </div>
              </aside>

              {/* ─── Right column ────────────────────────────────── */}
              <section className="pgp__right">
                <h1 className="pgp__title">{group.display_title}</h1>

                <p className="pgp__store-count">
                  Dostupno u{' '}
                  <strong>{group.stores.length}</strong>
                  {' '}{group.stores.length === 1 ? 'dućanu' : group.stores.length < 5 ? 'dućana' : 'dućana'}
                </p>

                <div className="pgp__price-row">
                  <span className="pgp__price-label">Od</span>
                  <span className="pgp__price-min">
                    {group.min_price.toFixed(2).replace('.', ',')} €
                  </span>
                  {group.stores.length > 1 && (
                    <>
                      <span className="pgp__price-label">do</span>
                      <span className="pgp__price-max">
                        {group.max_price.toFixed(2).replace('.', ',')} €
                      </span>
                    </>
                  )}
                </div>

                {/* Price comparison table */}
                <div className="pgp__table-section">
                  <h2 className="pgp__section-heading">Usporedba cijena</h2>
                  <PriceComparisonTable stores={group.stores} />
                </div>

                {/* Savings summary */}
                {group.stores.length > 1 && group.usteda > 0.01 && cheapestStore && (
                  <div className="pgp__savings">
                    <span className="pgp__savings-icon" aria-hidden="true">💰</span>
                    <span>
                      Uštedi do{' '}
                      <strong className="pgp__savings-amount">
                        {group.usteda.toFixed(2).replace('.', ',')} €
                      </strong>
                      {' '}({group.usteda_posto.toFixed(0)}%) kupnjom na{' '}
                      <strong>{cheapestStore.store_display_name}</strong>
                    </span>
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      </main>
    </>
  )
}
