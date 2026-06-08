import type { StorePrice } from '../api/types'
import './PriceComparisonTable.css'

interface Props {
  stores: StorePrice[]
}

export default function PriceComparisonTable({ stores }: Props) {
  const sorted = [...stores].sort((a, b) => a.price - b.price)

  return (
    <div className="pct">
      <table className="pct__table" aria-label="Usporedba cijena po dućanima">
        <thead>
          <tr>
            <th className="pct__th pct__th--img" aria-label="Slika" />
            <th className="pct__th">Dućan</th>
            <th className="pct__th pct__th--price">Cijena</th>
            <th className="pct__th pct__th--title">Naziv u dućanu</th>
            <th className="pct__th pct__th--action">Kupnja</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => (
            <tr
              key={s.store_name}
              className={`pct__row ${s.is_cheapest ? 'pct__row--cheapest' : ''}`}
            >
              <td className="pct__td pct__td--img">
                {s.image_url && (
                  <img
                    src={s.image_url}
                    alt=""
                    className="pct__thumb"
                    onError={(e) => { e.currentTarget.style.display = 'none' }}
                    loading="lazy"
                  />
                )}
              </td>
              <td className="pct__td pct__td--store">
                <span className="pct__store-name">{s.store_display_name}</span>
                {s.is_cheapest && (
                  <span className="pct__cheapest-badge" aria-label="Najjeftinije">
                    ⭐ Najjeftinije
                  </span>
                )}
              </td>
              <td className="pct__td pct__td--price">
                <span className="pct__price">{s.price_original}</span>
              </td>
              <td className="pct__td pct__td--title">
                <span className="pct__product-title">{s.product_title}</span>
              </td>
              <td className="pct__td pct__td--action">
                {s.product_url ? (
                  <a
                    href={s.product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="pct__buy-link"
                    aria-label={`Kupi na ${s.store_display_name}`}
                  >
                    Kupi <span aria-hidden="true">→</span>
                  </a>
                ) : (
                  <span className="pct__no-link">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
