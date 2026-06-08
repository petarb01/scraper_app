import { useSearchParams } from 'react-router-dom'
import type { Category } from '../api/types'
import { CATEGORY_META } from '../api/categoryIcons'
import './FilterSidebar.css'

interface FilterSidebarProps {
  categories: Category[]
  preserveParams?: string[]
}

const VOLUME_OPTIONS = [
  { value: '', label: 'Sve veličine' },
  { value: '200',  label: '200 ml' },
  { value: '350',  label: '350 ml' },
  { value: '500',  label: '500 ml' },
  { value: '700',  label: '700 ml' },
  { value: '1000', label: '1L' },
  { value: '1500', label: '1.5L' },
  { value: '3000', label: '3L' },
]

export default function FilterSidebar({ categories, preserveParams }: FilterSidebarProps) {
  const [params, setParams] = useSearchParams()

  // Read current filter state from URL
  const selectedCategories = params.getAll('kategorija')
  const minCijena = params.get('min_cijena') ?? ''
  const maxCijena = params.get('max_cijena') ?? ''
  const volumen   = params.get('volumen') ?? ''
  const ducani    = params.get('ducani') ?? ''

  function setParam(key: string, value: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      next.set('stranica', '1') // reset to page 1 on filter change
      return next
    })
  }

  function toggleCategory(slug: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      const current = next.getAll('kategorija')
      next.delete('kategorija')
      if (current.includes(slug)) {
        current.filter((s) => s !== slug).forEach((s) => next.append('kategorija', s))
      } else {
        [...current, slug].forEach((s) => next.append('kategorija', s))
      }
      next.set('stranica', '1')
      return next
    })
  }

  function reset() {
    setParams((prev) => {
      const next = new URLSearchParams({ stranica: '1' })
      preserveParams?.forEach((key) => {
        const val = prev.get(key)
        if (val) next.set(key, val)
      })
      return next
    })
  }

  const hasActiveFilters =
    selectedCategories.length > 0 ||
    minCijena !== '' ||
    maxCijena !== '' ||
    volumen !== '' ||
    ducani !== ''

  return (
    <aside className="filter-sidebar" aria-label="Filteri pretrage">
      {/* Header */}
      <div className="filter-sidebar__header">
        <span className="filter-sidebar__title">Filteri</span>
        {hasActiveFilters && (
          <button className="filter-sidebar__reset" onClick={reset} type="button">
            Resetiraj
          </button>
        )}
      </div>

      {/* Categories */}
      <section className="filter-sidebar__section">
        <h3 className="filter-sidebar__label">Kategorija</h3>
        <ul className="filter-sidebar__checklist">
          {categories.map((cat) => {
            const checked = selectedCategories.includes(cat.slug)
            const icon = CATEGORY_META[cat.slug]?.icon ?? '🍾'
            return (
              <li key={cat.slug}>
                <label className={`filter-check ${checked ? 'filter-check--active' : ''}`}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleCategory(cat.slug)}
                    className="filter-check__input"
                  />
                  <span className="filter-check__icon" aria-hidden="true">{icon}</span>
                  <span className="filter-check__name">{cat.display_name}</span>
                  <span className="filter-check__count">{cat.product_count}</span>
                </label>
              </li>
            )
          })}
        </ul>
      </section>

      {/* Price range */}
      <section className="filter-sidebar__section">
        <h3 className="filter-sidebar__label">Cijena (€)</h3>
        <div className="filter-price">
          <input
            type="number"
            className="filter-price__input"
            placeholder="Min"
            min={0}
            step={0.5}
            value={minCijena}
            onChange={(e) => setParam('min_cijena', e.target.value)}
            aria-label="Minimalna cijena"
          />
          <span className="filter-price__sep">–</span>
          <input
            type="number"
            className="filter-price__input"
            placeholder="Max"
            min={0}
            step={0.5}
            value={maxCijena}
            onChange={(e) => setParam('max_cijena', e.target.value)}
            aria-label="Maksimalna cijena"
          />
        </div>
      </section>

      {/* Volume */}
      <section className="filter-sidebar__section">
        <h3 className="filter-sidebar__label">Volumen</h3>
        <select
          className="filter-select"
          value={volumen}
          onChange={(e) => setParam('volumen', e.target.value)}
          aria-label="Filtriraj po volumenu"
        >
          {VOLUME_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </section>

      {/* Only comparable */}
      <section className="filter-sidebar__section">
        <label className="filter-toggle">
          <input
            type="checkbox"
            className="filter-check__input"
            checked={ducani === '2'}
            onChange={(e) => setParam('ducani', e.target.checked ? '2' : '')}
          />
          <div className="filter-toggle__body">
            <span className="filter-toggle__name">Samo usporedivi</span>
            <span className="filter-toggle__desc">Dostupno u ≥2 dućana</span>
          </div>
        </label>
      </section>
    </aside>
  )
}
