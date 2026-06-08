import { Link } from 'react-router-dom'
import logoSvg from '../assets/cijena_bar_logo.svg'
import './Footer.css'

// Each link is either a SPA route (to) or an anchor/external (href).
interface FooterLink {
  label: string
  to?: string
  href?: string
}

interface FooterCol {
  heading: string
  links: FooterLink[]
}

const cols: FooterCol[] = [
  {
    heading: 'Kategorije',
    links: [
      { label: 'Whisky',  to: '/pregled?kategorija=whisky' },
      { label: 'Vodka',   to: '/pregled?kategorija=vodka' },
      { label: 'Gin',     to: '/pregled?kategorija=gin' },
      { label: 'Rum',     to: '/pregled?kategorija=rum' },
      { label: 'Tequila', to: '/pregled?kategorija=tequila' },
      { label: 'Vino',    to: '/pregled?kategorija=vino' },
      { label: 'Pivo',    to: '/pregled?kategorija=pivo' },
    ],
  },
  {
    heading: 'Stranice',
    links: [
      { label: 'Sve ponude',          to: '/pregled' },
      { label: 'Novi proizvodi',      to: '/pregled' },
      { label: 'Najveća ušteda', to: '/pregled?sortiraj=usteda_pad' },
      { label: 'O projektu',          href: '/#kako-radi' },
    ],
  },
  {
    heading: 'Podrška',
    links: [
      { label: 'Kako radi?',       href: '/#kako-radi' },
      { label: 'Prijavi grešku',   href: '#' },
      { label: 'Prijedlog dućana', href: '#' },
      { label: 'Kontakt',          href: '#' },
    ],
  },
]

function FooterLinkItem({ link }: { link: FooterLink }) {
  if (link.to) {
    return <Link to={link.to} className="footer__link">{link.label}</Link>
  }
  return <a href={link.href ?? '#'} className="footer__link">{link.label}</a>
}

export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="footer">
      <div className="footer__inner container">
        {/* Brand */}
        <div className="footer__brand">
          <Link to="/" className="footer__logo">
            <img src={logoSvg} alt="CijenaBar" className="footer__logo-img" />
          </Link>
          <p className="footer__tagline">
            Uspoređujemo cijene alkohola u svim popularnim web&#8209;dućanima u Hrvatskoj.
            Bez registracije, bez naknada.
          </p>
          <p className="footer__disclaimer">
            Napomena: Cijena Bar nije webshop. Preusmjeravamo te na dućan s najboljom cijenom.
          </p>
        </div>

        {/* Link columns */}
        {cols.map((col) => (
          <nav key={col.heading} className="footer__col" aria-label={col.heading}>
            <h3 className="footer__col-heading">{col.heading}</h3>
            <ul>
              {col.links.map((link) => (
                <li key={link.label}>
                  <FooterLinkItem link={link} />
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>

      {/* Bottom bar */}
      <div className="footer__bar">
        <div className="container footer__bar-inner">
          <span>© {year} Cijena Bar. Sva prava pridržana.</span>
          <div className="footer__bar-links">
            <a href="#" className="footer__link">Uvjeti korištenja</a>
            <a href="#" className="footer__link">Privatnost</a>
            <a href="#" className="footer__link">Kolačići</a>
          </div>
        </div>
      </div>
    </footer>
  )
}
