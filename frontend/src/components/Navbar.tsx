import { useState, useEffect } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import logoSvg from '../assets/cijena_bar_logo.svg'
import './Navbar.css'

// Route links navigate to a SPA path. Hash links scroll to a section on the landing
// page or jump to /#section from any other page.
type NavItem =
  | { label: string; to: string; hash?: never }
  | { label: string; hash: string; to?: never }

const navLinks: NavItem[] = [
  { label: 'Proizvodi',  to: '/pregled' },
  { label: 'Dućani',    hash: 'ducani' },
  { label: 'Kako radi?', hash: 'kako-radi' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const location  = useLocation()
  const navigate  = useNavigate()
  const isLanding = location.pathname === '/'

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  /**
   * On the landing page: smooth-scroll to the hero search bar.
   * On any other page: navigate to /pretraga.
   */
  function handleSearch() {
    setMenuOpen(false)
    if (isLanding) {
      document.getElementById('pretraga')?.scrollIntoView({ behavior: 'smooth' })
    } else {
      navigate('/pretraga')
    }
  }

  function renderLink(item: NavItem, extraClass: string, onClick?: () => void) {
    if (item.to) {
      return (
        <Link key={item.to + item.label} to={item.to} className={extraClass} onClick={onClick}>
          {item.label}
        </Link>
      )
    }
    // Hash link: scroll in-page on landing, or navigate to /#hash on other pages
    const href = isLanding ? `#${item.hash}` : `/#${item.hash}`
    return (
      <a key={item.hash} href={href} className={extraClass} onClick={onClick}>
        {item.label}
      </a>
    )
  }

  return (
    <header className={`navbar ${scrolled ? 'navbar--scrolled' : ''}`}>
      <div className="navbar__inner container">
        {/* Logo */}
        <Link to="/" className="navbar__logo">
          <img src={logoSvg} alt="CijenaBar" className="navbar__logo-img" />
        </Link>

        {/* Desktop nav */}
        <nav className="navbar__nav" aria-label="Glavna navigacija">
          {navLinks.map((item) => renderLink(item, 'navbar__link'))}
        </nav>

        {/* CTA */}
        <div className="navbar__actions">
          <button className="btn btn--primary" type="button" onClick={handleSearch}>
            Pretraži
          </button>
        </div>

        {/* Hamburger */}
        <button
          className={`navbar__burger ${menuOpen ? 'navbar__burger--open' : ''}`}
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Otvori izbornik"
          aria-expanded={menuOpen}
        >
          <span /><span /><span />
        </button>
      </div>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="navbar__drawer">
          {navLinks.map((item) =>
            renderLink(item, 'navbar__drawer-link', () => setMenuOpen(false))
          )}
          <button
            className="btn btn--primary navbar__drawer-cta"
            type="button"
            onClick={handleSearch}
          >
            Pretraži
          </button>
        </div>
      )}
    </header>
  )
}
