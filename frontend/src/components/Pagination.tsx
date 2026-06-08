import './Pagination.css'

interface PaginationProps {
  page: number
  pages: number
  total: number
  limit: number
  onPageChange: (page: number) => void
}

/** Generates the sequence of page-number tokens to display. */
function buildPages(current: number, total: number): (number | '...')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)

  const pages: (number | '...')[] = [1]

  const rangeStart = Math.max(2, current - 2)
  const rangeEnd   = Math.min(total - 1, current + 2)

  if (rangeStart > 2) pages.push('...')
  for (let i = rangeStart; i <= rangeEnd; i++) pages.push(i)
  if (rangeEnd < total - 1) pages.push('...')

  pages.push(total)
  return pages
}

export default function Pagination({ page, pages, total, limit, onPageChange }: PaginationProps) {
  if (pages <= 1) return null

  const tokens = buildPages(page, pages)
  const start = (page - 1) * limit + 1
  const end   = Math.min(page * limit, total)

  return (
    <nav className="pagination" aria-label="Straničenje">
      <span className="pagination__info">
        {start}–{end} od {total}
      </span>

      <div className="pagination__controls">
        <button
          className="pagination__btn"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Prethodna stranica"
        >
          ‹
        </button>

        {tokens.map((token, idx) =>
          token === '...' ? (
            <span key={`ellipsis-${idx}`} className="pagination__ellipsis">…</span>
          ) : (
            <button
              key={token}
              className={`pagination__btn ${token === page ? 'pagination__btn--active' : ''}`}
              onClick={() => onPageChange(token)}
              aria-label={`Stranica ${token}`}
              aria-current={token === page ? 'page' : undefined}
            >
              {token}
            </button>
          )
        )}

        <button
          className="pagination__btn"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          aria-label="Sljedeća stranica"
        >
          ›
        </button>
      </div>
    </nav>
  )
}
