import './Skeleton.css'

/** Base shimmer block — pass className to size it. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

/** Skeleton shaped like a ProductCard for browse/search grids. */
export function ProductCardSkeleton() {
  return (
    <div className="pc-skeleton" aria-hidden="true">
      <Skeleton className="pc-skeleton__image" />
      <div className="pc-skeleton__body">
        <Skeleton className="pc-skeleton__badge" />
        <Skeleton className="pc-skeleton__title" />
        <Skeleton className="pc-skeleton__title pc-skeleton__title--short" />
        <Skeleton className="pc-skeleton__price" />
      </div>
    </div>
  )
}
