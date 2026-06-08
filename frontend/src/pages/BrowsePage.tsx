import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Navbar from '../components/Navbar'
import FilterSidebar from '../components/FilterSidebar'
import ProductGrid from '../components/ProductGrid'
import Pagination from '../components/Pagination'
import { useGroups, useCategories } from '../api/hooks'
import type { BrowseFilters } from '../api/types'
import './BrowsePage.css'

const SORT_OPTIONS = [
  { value: 'naziv_rast',  label: 'Naziv A–Z' },
  { value: 'naziv_pad',   label: 'Naziv Z–A' },
  { value: 'cijena_rast', label: 'Cijena ↑' },
  { value: 'cijena_pad',  label: 'Cijena ↓' },
  { value: 'usteda_pad',  label: 'Najveća ušteda' },
] as const

const LIMIT = 24

export default function BrowsePage() {
  const [params, setParams] = useSearchParams()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Read URL params into filter values
  const kategorija = params.getAll('kategorija')
  const min_cijena = params.get('min_cijena') ? Number(params.get('min_cijena')) : undefined
  const max_cijena = params.get('max_cijena') ? Number(params.get('max_cijena')) : undefined
  const volumen    = params.get('volumen')     ? Number(params.get('volumen'))    : undefined
  const ducani     = params.get('ducani')      ? Number(params.get('ducani'))     : undefined
  const sortiraj   = params.get('sortiraj') as BrowseFilters['sortiraj'] | null
  const page       = Math.max(1, Number(params.get('stranica') ?? 1))

  const filters: BrowseFilters = {
    kategorija: kategorija.length > 0 ? kategorija : undefined,
    min_cijena,
    max_cijena,
    volumen,
    ducani,
    sortiraj: sortiraj ?? undefined,
    page,
    limit: LIMIT,
  }

  const { data, isLoading, isError, refetch } = useGroups(filters)
  const { data: catData } = useCategories()

  const categories = catData?.data ?? []
  const groups     = data?.data
  const pagination = data?.pagination

  function setPage(p: number) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('stranica', String(p))
      return next
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function setSort(value: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set('sortiraj', value)
      else next.delete('sortiraj')
      next.set('stranica', '1')
      return next
    })
  }

  function removeParam(key: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete(key)
      next.set('stranica', '1')
      return next
    })
  }

  // Build active filter chips for display
  const chips: { label: string; remove: () => void }[] = []

  kategorija.forEach((slug) => {
    const cat = categories.find((c) => c.slug === slug)
    chips.push({
      label: cat?.display_name ?? slug,
      remove: () =>
        setParams((prev) => {
          const next = new URLSearchParams(prev)
          next.delete('kategorija')
          kategorija.filter((s) => s !== slug).forEach((s) => next.append('kategorija', s))
          next.set('stranica', '1')
          return next
        }),
    })
  })

  if (min_cijena !== undefined)
    chips.push({ label: `od ${min_cijena}€`, remove: () => removeParam('min_cijena') })
  if (max_cijena !== undefined)
    chips.push({ label: `do ${max_cijena}€`, remove: () => removeParam('max_cijena') })
  if (volumen !== undefined)
    chips.push({ label: formatVolume(volumen), remove: () => removeParam('volumen') })
  if (ducani === 2)
    chips.push({ label: 'Samo usporedivi', remove: () => removeParam('ducani') })

  const total = pagination?.total
  const totalLabel = total !== undefined
    ? `${total.toLocaleString('hr-HR')} ${total === 1 ? 'proizvod' : 'proizvoda'}`
    : null

  return (
    <>
      <Navbar />

      <div className="browse-page">
        <div className="browse-page__inner container">

          {/* Mobile filter toggle button */}
          <button
            className="browse-page__filter-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            type="button"
            aria-expanded={sidebarOpen}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="4" y1="6" x2="20" y2="6" />
              <line x1="4" y1="12" x2="14" y2="12" />
              <line x1="4" y1="18" x2="10" y2="18" />
            </svg>
            Filteri
            {chips.length > 0 && (
              <span className="browse-page__filter-badge">{chips.length}</span>
            )}
          </button>

          <div className="browse-page__layout">
            {/* Sidebar */}
            <div className={`browse-page__sidebar ${sidebarOpen ? 'browse-page__sidebar--open' : ''}`}>
              <FilterSidebar categories={categories} />
            </div>

            {/* Main content */}
            <main className="browse-page__main">
              {/* Top bar: heading + count + sort */}
              <div className="browse-topbar">
                <div className="browse-topbar__left">
                  <h1 className="browse-topbar__heading">Pregled proizvoda</h1>
                  {totalLabel && (
                    <span className="browse-topbar__count">{totalLabel}</span>
                  )}
                </div>
                <div className="browse-topbar__right">
                  <label className="browse-topbar__sort-label" htmlFor="browse-sort">
                    Sortiraj:
                  </label>
                  <select
                    id="browse-sort"
                    className="browse-topbar__sort"
                    value={sortiraj ?? 'naziv_rast'}
                    onChange={(e) => setSort(e.target.value)}
                  >
                    {SORT_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Active filter chips */}
              {chips.length > 0 && (
                <div className="browse-chips" role="list" aria-label="Aktivni filteri">
                  {chips.map((chip) => (
                    <span key={chip.label} className="browse-chip" role="listitem">
                      {chip.label}
                      <button
                        className="browse-chip__remove"
                        onClick={chip.remove}
                        type="button"
                        aria-label={`Ukloni filter: ${chip.label}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                  <button
                    className="browse-chips__clear"
                    onClick={() => setParams({ stranica: '1' })}
                    type="button"
                  >
                    Ukloni sve
                  </button>
                </div>
              )}

              {/* Product grid */}
              <ProductGrid
                groups={groups}
                isLoading={isLoading}
                isError={isError}
                onRetry={() => refetch()}
                skeletonCount={LIMIT}
              />

              {/* Pagination */}
              {pagination && (
                <Pagination
                  page={page}
                  pages={pagination.pages}
                  total={pagination.total}
                  limit={LIMIT}
                  onPageChange={setPage}
                />
              )}
            </main>
          </div>
        </div>
      </div>
    </>
  )
}

function formatVolume(ml: number): string {
  if (ml >= 1000 && ml % 1000 === 0) return `${ml / 1000}L`
  if (ml >= 1000) return `${(ml / 1000).toFixed(1)}L`
  return `${ml}ml`
}
