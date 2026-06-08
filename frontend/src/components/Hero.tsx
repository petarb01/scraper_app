import { useState, useEffect, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAutocomplete } from '../api/hooks'
import { getCategoryMeta, groupDetailUrl } from '../api/categoryIcons'
import './Hero.css'

const CATEGORY_OPTIONS = [
  { value: '',        label: 'Sve kategorije' },
  { value: 'whisky',  label: 'Whisky' },
  { value: 'vodka',   label: 'Vodka' },
  { value: 'gin',     label: 'Gin' },
  { value: 'rum',     label: 'Rum' },
  { value: 'tequila', label: 'Tequila' },
  { value: 'vino',    label: 'Vino' },
  { value: 'pivo',    label: 'Pivo' },
  { value: 'konjak',  label: 'Konjak' },
  { value: 'rakija',  label: 'Rakija' },
  { value: 'likeri',  label: 'Likeri' },
  { value: 'kokteli', label: 'Kokteli' },
]

const QUICK_TAGS = [
  'Chivas Regal', 'Jameson', 'Bombay Sapphire',
  'Grey Goose', 'Jägermeister', 'Prosek',
]

export default function Hero() {
  const navigate = useNavigate()
  const wrapRef  = useRef<HTMLDivElement>(null)

  const [query,       setQuery]       = useState('')
  const [category,    setCategory]    = useState('')
  const [debounced,   setDebounced]   = useState('')
  const [open,        setOpen]        = useState(false)
  const [highlighted, setHighlighted] = useState(-1)

  // Debounce query by 300 ms before firing autocomplete
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300)
    return () => clearTimeout(t)
  }, [query])

  const { data: acData } = useAutocomplete(debounced)
  const suggestions     = (acData?.data ?? []).slice(0, 4)
  const dropdownVisible = open && debounced.length >= 2 && suggestions.length > 0

  // Close dropdown on outside click
  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [])

  function doSearch(q: string, cat?: string) {
    const trimmed = q.trim()
    if (!trimmed) return
    const p = new URLSearchParams({ q: trimmed })
    const resolvedCat = cat !== undefined ? cat : category
    if (resolvedCat) p.set('kategorija', resolvedCat)
    navigate(`/pretraga?${p.toString()}`)
    setOpen(false)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setHighlighted((h) => Math.min(h + 1, suggestions.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setHighlighted((h) => Math.max(h - 1, -1))
        break
      case 'Enter':
        e.preventDefault()
        if (dropdownVisible && highlighted >= 0) {
          navigate(groupDetailUrl(suggestions[highlighted].group_id))
          setOpen(false)
        } else {
          doSearch(query)
        }
        break
      case 'Escape':
        setOpen(false)
        setHighlighted(-1)
        break
    }
  }

  return (
    <section className="hero" id="pretraga">
      {/* Decorative blobs — clipped inside their own overflow:hidden wrapper */}
      <div className="hero__blobs" aria-hidden="true">
        <div className="hero__blob hero__blob--1" />
        <div className="hero__blob hero__blob--2" />
        <div className="hero__blob hero__blob--3" />
      </div>

      <div className="hero__inner container">
        <div className="hero__badge badge badge--gold">
          <span>✦</span>
          5 dućana · 4 500+ proizvoda
        </div>

        <h1 className="hero__title">
          Pronađi najjeftinija<br />
          <span className="hero__title-accent">pića u Hrvatskoj</span>
        </h1>

        <p className="hero__subtitle">
          Uspoređujemo cijene alkohola u svim popularnim web&nbsp;dućanima.
          Uštedi bez da pretražuješ svaku stranicu zasebno.
        </p>

        {/* Search bar */}
        <div className="hero__search-wrap" ref={wrapRef}>
          <div className="hero__search">

            {/* Category select */}
            <div className="hero__search-category">
              <select
                className="hero__search-select"
                aria-label="Odaberi kategoriju"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {CATEGORY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            <div className="hero__search-divider" aria-hidden="true" />

            {/* Text input */}
            <input
              className="hero__search-input"
              type="search"
              placeholder="Pretraži – npr. Chivas Regal 18, Hendricks…"
              aria-label="Pretraži piće"
              aria-autocomplete="list"
              aria-expanded={dropdownVisible}
              aria-haspopup="listbox"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setHighlighted(-1)
                setOpen(true)
              }}
              onFocus={() => {
                if (query.length >= 2) setOpen(true)
              }}
              onKeyDown={handleKeyDown}
            />

            {/* Search button */}
            <button
              className="hero__search-btn btn btn--primary"
              type="button"
              onClick={() => doSearch(query)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
              </svg>
              Pretraži
            </button>
          </div>

          {/* Autocomplete dropdown */}
          {dropdownVisible && (
            <ul
              className="hero__autocomplete"
              role="listbox"
              aria-label="Prijedlozi pretrage"
            >
              {suggestions.map((s, i) => {
                const meta = getCategoryMeta(s.category_name?.toLowerCase())
                return (
                  <li
                    key={s.group_id}
                    className={`hero__ac-item ${i === highlighted ? 'hero__ac-item--active' : ''}`}
                    role="option"
                    aria-selected={i === highlighted}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      navigate(groupDetailUrl(s.group_id))
                      setOpen(false)
                    }}
                    onMouseEnter={() => setHighlighted(i)}
                  >
                    <span className="hero__ac-icon" aria-hidden="true">{meta.icon}</span>
                    <span className="hero__ac-body">
                      <span className="hero__ac-title">{s.display_title}</span>
                      <span className="hero__ac-meta">
                        {s.category_name}
                        {s.min_price > 0 && ` · od ${s.min_price.toFixed(2)} €`}
                      </span>
                    </span>
                    <svg className="hero__ac-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Quick-search tags — navigate to search with no category filter */}
        <div className="hero__tags" role="list">
          <span className="hero__tags-label">Popularno:</span>
          {QUICK_TAGS.map((tag) => (
            <button
              key={tag}
              className="hero__tag"
              role="listitem"
              type="button"
              onClick={() => doSearch(tag, '')}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      {/* Bottom fade */}
      <div className="hero__fade" aria-hidden="true" />
    </section>
  )
}
