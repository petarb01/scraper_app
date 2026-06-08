import { useParams, Link } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { Skeleton } from '../components/Skeleton'
import ErrorMessage from '../components/ErrorMessage'
import { useGroupDetail } from '../api/hooks'
import { getCategoryMeta } from '../api/categoryIcons'
import './ProductGroupPage.css'
import './ProductSingletonPage.css'

function formatVolume(ml: number | null): string {
  if (!ml) return ''
  if (ml >= 1000 && ml % 1000 === 0) return `${ml / 1000} L`
  if (ml >= 1000) return `${(ml / 1000).toFixed(1)} L`
  return `${ml} ml`
}

export default function ProductSingletonPage() {
  const { productId } = useParams<{ productId: string }>()
  const groupId = `p${productId ?? ''}`

  const { data, isLoading, isError, refetch } = useGroupDetail(groupId)
  const group = data?.data

  const meta = getCategoryMeta(group?.category_slug)
  const store = group?.stores[0] ?? null

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
                  {store?.image_url ? (
                    <img
                      src={store.image_url}
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
                      display: store?.image_url ? 'none' : 'flex',
                    }}
                  >
                    <span className="pgp__image-icon" aria-hidden="true">{meta.icon}</span>
                  </div>
                </div>

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

                {/* Single-store notice */}
                <div className="psp__notice" role="note">
                  <span aria-hidden="true">ℹ️</span>
                  Ovaj proizvod je dostupan samo u jednom dućanu.
                </div>

                {/* Store info */}
                {store && (
                  <div className="psp__store-card">
                    <div className="psp__store-header">
                      <span className="psp__store-name">{store.store_display_name}</span>
                      <span className="psp__price">{store.price_original}</span>
                    </div>
                    <p className="psp__product-title">{store.product_title}</p>
                    {store.product_url && (
                      <a
                        href={store.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn--primary psp__buy-btn"
                        aria-label={`Kupi na ${store.store_display_name}`}
                      >
                        Kupi na {store.store_display_name} →
                      </a>
                    )}
                  </div>
                )}

                <div className="psp__browse-cta">
                  <p className="psp__browse-text">Traži slične proizvode u više dućana?</p>
                  <Link
                    to={`/pregled?kategorija=${group.category_slug}`}
                    className="btn btn--ghost"
                  >
                    Pregledaj {group.category_name}
                  </Link>
                </div>
              </section>
            </div>
          )}
        </div>
      </main>
    </>
  )
}
