import { Link } from 'react-router-dom'
import { useCategories } from '../api/hooks'
import { getCategoryMeta } from '../api/categoryIcons'
import { Skeleton } from './Skeleton'
import './Categories.css'

// Fallback slugs/names used when the API fails or returns nothing
const FALLBACK = [
  { slug: 'whisky',  display_name: 'Whisky',  product_count: 0 },
  { slug: 'vodka',   display_name: 'Vodka',   product_count: 0 },
  { slug: 'gin',     display_name: 'Gin',      product_count: 0 },
  { slug: 'rum',     display_name: 'Rum',      product_count: 0 },
  { slug: 'tequila', display_name: 'Tequila', product_count: 0 },
  { slug: 'konjak',  display_name: 'Konjak',  product_count: 0 },
  { slug: 'rakija',  display_name: 'Rakija',  product_count: 0 },
  { slug: 'likeri',  display_name: 'Likeri',  product_count: 0 },
  { slug: 'vino',    display_name: 'Vino',    product_count: 0 },
  { slug: 'pivo',    display_name: 'Pivo',    product_count: 0 },
  { slug: 'kokteli', display_name: 'Kokteli', product_count: 0 },
]

const SKELETON_SLOTS = Array.from({ length: 11 })

export default function Categories() {
  const { data, isLoading, isError } = useCategories()
  const apiCategories = data?.data ?? []

  // Use fallback list on error or empty API response (API counts remain 0)
  const displayList = isError || (!isLoading && apiCategories.length === 0)
    ? FALLBACK
    : apiCategories.map((c) => ({
        slug: c.slug,
        display_name: c.display_name,
        product_count: c.product_count,
      }))

  return (
    <section className="categories section" id="kategorije">
      <div className="container">
        <header className="section-header">
          <div className="badge badge--gold" style={{ marginBottom: '1rem' }}>Kategorije</div>
          <h2>Što tražiš večeras?</h2>
          <p>Pregledaj ponudu po vrsti pića i odmah pronađi najbolju cijenu.</p>
        </header>

        <ul className="categories__grid">
          {isLoading
            ? SKELETON_SLOTS.map((_, i) => (
                <li key={i} aria-hidden="true">
                  <div className="category-card category-card--skeleton">
                    <Skeleton className="cat-sk__icon" />
                    <Skeleton className="cat-sk__label" />
                    <Skeleton className="cat-sk__count" />
                  </div>
                </li>
              ))
            : displayList.map((cat) => {
                const meta = getCategoryMeta(cat.slug)
                return (
                  <li key={cat.slug}>
                    <Link
                      to={`/pregled?kategorija=${cat.slug}`}
                      className="category-card"
                      aria-label={
                        cat.product_count > 0
                          ? `${cat.display_name} \u2013 ${cat.product_count} proizvoda`
                          : cat.display_name
                      }
                    >
                      <div
                        className="category-card__glow"
                        style={{ background: meta.gradient }}
                        aria-hidden="true"
                      />
                      <span className="category-card__icon" aria-hidden="true">{meta.icon}</span>
                      <strong className="category-card__label">{cat.display_name}</strong>
                      {cat.product_count > 0 && (
                        <span className="category-card__count">{cat.product_count} proizvoda</span>
                      )}
                    </Link>
                  </li>
                )
              })}
        </ul>
      </div>
    </section>
  )
}
