import type { ProductGroup } from '../api/types'
import ProductCard from './ProductCard'
import { ProductCardSkeleton } from './Skeleton'
import ErrorMessage from './ErrorMessage'
import EmptyState from './EmptyState'
import './ProductGrid.css'

interface ProductGridProps {
  groups: ProductGroup[] | undefined
  isLoading: boolean
  isError: boolean
  onRetry?: () => void
  emptyTitle?: string
  emptyDescription?: string
  skeletonCount?: number
}

export default function ProductGrid({
  groups,
  isLoading,
  isError,
  onRetry,
  emptyTitle,
  emptyDescription,
  skeletonCount = 24,
}: ProductGridProps) {
  if (isLoading) {
    return (
      <div className="product-grid">
        {Array.from({ length: skeletonCount }, (_, i) => (
          <ProductCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (isError) {
    return <ErrorMessage message="Nismo mogli učitati proizvode." onRetry={onRetry} />
  }

  if (!groups || groups.length === 0) {
    return (
      <EmptyState
        title={emptyTitle ?? 'Nema pronađenih proizvoda'}
        description={emptyDescription ?? 'Pokušaj s drugačijim filterima ili pojmom pretrage.'}
      />
    )
  }

  return (
    <div className="product-grid">
      {groups.map((group) => (
        <ProductCard key={group.group_id} group={group} />
      ))}
    </div>
  )
}
