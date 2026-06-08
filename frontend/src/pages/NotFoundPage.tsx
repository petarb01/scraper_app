import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <main style={{ padding: '6rem 2rem 2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
      <h1 style={{ fontSize: '4rem', color: 'var(--gold-400)' }}>404</h1>
      <h2 style={{ marginBottom: '1rem' }}>Stranica nije pronađena</h2>
      <p style={{ marginBottom: '2rem' }}>Stranica koju tražiš ne postoji ili je premještena.</p>
      <Link to="/" className="btn btn--primary">Povratak na početnu</Link>
    </main>
  )
}
