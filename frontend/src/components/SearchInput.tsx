import { useState, useEffect, useRef } from 'react'
import type { KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAutocomplete } from '../api/hooks'
import { getCategoryMeta, groupDetailUrl } from '../api/categoryIcons'
import './SearchInput.css'

interface SearchInputProps {
  /** Pre-filled search term (e.g. from URL ?q=) */
  defaultValue?: string
  /** Called when the user submits a new query */
  onSearch: (query: string) => void
  placeholder?: string
  autoFocus?: boolean
}

export default function SearchInput({
  defaultValue = '',
  onSearch,
  placeholder = 'Pretraži proizvode…',
  autoFocus = false,
}: SearchInputProps) {
  const navigate = useNavigate()
  const wrapRef  = useRef<HTMLDivElement>(null)

  const [query,       setQuery]       = useState(defaultValue)
  const [debounced,   setDebounced]   = useState(defaultValue)
  const [open,        setOpen]        = useState(false)
  const [highlighted, setHighlighted] = useState(-1)

  // Keep input in sync when the parent's defaultValue changes (new search)
  useEffect(() => {
    setQuery(defaultValue)
    setDebounced(defaultValue)
  }, [defaultValue])

  // Debounce 300 ms
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300)
    return () => clearTimeout(t)
  }, [query])

  const { data: acData } = useAutocomplete(debounced)
  const suggestions     = acData?.data ?? []
  const dropdownVisible = open && debounced.length >= 2 && suggestions.length > 0

  // Close on outside click
  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [])

  function handleSubmit() {
    const trimmed = query.trim()
    if (trimmed) {
      onSearch(trimmed)
      setOpen(false)
    }
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
          handleSubmit()
        }
        break
      case 'Escape':
        setOpen(false)
        setHighlighted(-1)
        break
    }
  }

  return (
    <div className="search-input" ref={wrapRef}>
      <div className="search-input__bar">
        <svg className="search-input__icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
        </svg>

        <input
          className="search-input__field"
          type="search"
          placeholder={placeholder}
          aria-label="Pretraži piće"
          aria-autocomplete="list"
          aria-expanded={dropdownVisible}
          aria-haspopup="listbox"
          value={query}
          autoFocus={autoFocus}
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

        {query && (
          <button
            className="search-input__clear"
            type="button"
            onClick={() => { setQuery(''); setOpen(false) }}
            aria-label="Očisti pretragu"
          >
            ×
          </button>
        )}

        <button
          className="search-input__btn btn btn--primary"
          type="button"
          onClick={handleSubmit}
        >
          Pretraži
        </button>
      </div>

      {/* Autocomplete dropdown */}
      {dropdownVisible && (
        <ul
          className="search-input__dropdown"
          role="listbox"
          aria-label="Prijedlozi pretrage"
        >
          {suggestions.map((s, i) => {
            const meta = getCategoryMeta(s.category_name?.toLowerCase())
            return (
              <li
                key={s.group_id}
                className={`search-input__option ${i === highlighted ? 'search-input__option--active' : ''}`}
                role="option"
                aria-selected={i === highlighted}
                onMouseDown={(e) => {
                  e.preventDefault()
                  navigate(groupDetailUrl(s.group_id))
                  setOpen(false)
                }}
                onMouseEnter={() => setHighlighted(i)}
              >
                <span className="search-input__opt-icon" aria-hidden="true">{meta.icon}</span>
                <span className="search-input__opt-body">
                  <span className="search-input__opt-title">{s.display_title}</span>
                  <span className="search-input__opt-meta">
                    {s.category_name}
                    {s.min_price > 0 && ` · od ${s.min_price.toFixed(2)} €`}
                  </span>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
