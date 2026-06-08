import { Link } from 'react-router-dom'
import type { ProductGroup } from '../api/types'
import { getCategoryMeta, groupDetailUrl } from '../api/categoryIcons'
import './ProductCard.css'

interface ProductCardProps {
  group: ProductGroup
}

export default function ProductCard({ group }: ProductCardProps) {
  const meta = getCategoryMeta(group.category_slug)
  const url = groupDetailUrl(group.group_id)
  const hasImage = Boolean(group.display_image_url)
  const hasSavings = group.store_count > 1 && group.usteda > 0.01

  return (
    <article className="pc">
      {/* Image / icon area */}
      <Link to={url} className="pc__image-wrap" tabIndex={-1} aria-hidden="true">
        {hasImage ? (
          <img
            src={group.display_image_url!}
            alt={group.display_title}
            className="pc__image"
            onError={(e) => {
              const t = e.currentTarget
              t.style.display = 'none'
              const fallback = t.nextElementSibling as HTMLElement | null
              if (fallback) fallback.style.display = 'flex'
            }}
            loading="lazy"
          />
        ) : null}
        <div
          className="pc__image-fallback"
          style={{ background: meta.gradient, display: hasImage ? 'none' : 'flex' }}
          aria-hidden="true"
        >
          <span>{meta.icon}</span>
        </div>
      </Link>

      {/* Body */}
      <div className="pc__body">
        {/* Category + volume */}
        <div className="pc__meta">
          <span className="pc__category">{group.category_name}</span>
          {group.volume_ml && (
            <span className="pc__volume">{formatVolume(group.volume_ml)}</span>
          )}
        </div>

        {/* Title */}
        <Link to={url} className="pc__title-link">
          <h3 className="pc__title">{group.display_title}</h3>
        </Link>

        {/* Price row */}
        <div className="pc__price-row">
          <div className="pc__price-group">
            <span className="pc__price-label">od</span>
            <span className="pc__price">{group.min_price.toFixed(2)} €</span>
          </div>
          <span className="pc__stores-badge">
            {group.store_count} {group.store_count === 1 ? 'dućan' : group.store_count < 5 ? 'dućana' : 'dućana'}
          </span>
        </div>

        {/* Savings + CTA */}
        <div className="pc__footer">
          {hasSavings ? (
            <span className="pc__savings">
              Uštedi do {group.usteda.toFixed(2)} €
            </span>
          ) : (
            <span />
          )}
          <Link to={url} className="btn btn--outline-gold pc__btn">
            {group.store_count > 1 ? 'Usporedi' : 'Pogledaj'}
          </Link>
        </div>
      </div>
    </article>
  )
}

function formatVolume(ml: number): string {
  if (ml >= 1000 && ml % 1000 === 0) return `${ml / 1000}L`
  if (ml >= 1000) return `${(ml / 1000).toFixed(1)}L`
  return `${ml}ml`
}
