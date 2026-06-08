import './HowItWorks.css'

const steps = [
  {
    number: '01',
    icon: '🔍',
    title: 'Pretraži',
    description:
      'Upiši naziv pića, marku ili kategoriju. Možeš filtrirati po vrsti pića, volumenu i cijeni.',
  },
  {
    number: '02',
    icon: '📊',
    title: 'Usporedi',
    description:
      'Prikazujemo cijene iz svih praćenih web-dućana usporedno — odmah vidiš gdje je najjeftinije.',
  },
  {
    number: '03',
    icon: '🛒',
    title: 'Kupi',
    description:
      'Jednim klikom prelazak na stranicu dućana s najboljom cijenom. Bez registracije, bez naknada.',
  },
]

const stores = [
  { name: 'Cugaklik',     url: 'https://www.cugaklik.hr',  emoji: '🏪' },
  { name: 'Diskont Fumar',url: 'https://diskontfumar.hr',  emoji: '🏪' },
  { name: 'E-Cuga',       url: 'https://ecuga.com',        emoji: '🏪' },
  { name: 'Promili',      url: 'https://promili.hr',       emoji: '🏪' },
  { name: 'Rotodinamic',  url: 'https://rotodinamic.hr',   emoji: '🏪' },
]

export default function HowItWorks() {
  return (
    <>
      {/* How it works */}
      <section className="how section" id="kako-radi">
        <div className="container">
          <header className="section-header">
            <div className="badge badge--gold" style={{ marginBottom: '1rem' }}>Jednostavno</div>
            <h2>Kako to radi?</h2>
            <p>Tri koraka do bolje cijene — i svaki traje manje od minute.</p>
          </header>

          <ol className="how__steps" aria-label="Koraci za korištenje">
            {steps.map((step) => (
              <li key={step.number} className="how__step">
                <div className="how__step-number" aria-hidden="true">{step.number}</div>
                <div className="how__step-icon" aria-hidden="true">{step.icon}</div>
                <h3 className="how__step-title">{step.title}</h3>
                <p className="how__step-desc">{step.description}</p>
              </li>
            ))}
          </ol>

          <div className="how__connector" aria-hidden="true" />
        </div>
      </section>

      {/* Stores banner */}
      <section className="stores section" id="ducani">
        <div className="container">
          <header className="section-header">
            <div className="badge badge--gold" style={{ marginBottom: '1rem' }}>Partneri</div>
            <h2>Pratimo <span className="stores__accent">5 dućana</span></h2>
            <p>Svaki dan osvježavamo cijene iz svih dućana kako bi podaci bili aktualni.</p>
          </header>

          <ul className="stores__grid">
            {stores.map((s) => (
              <li key={s.name}>
                <a
                  href={s.url}
                  className="store-chip"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`Posjeti ${s.name}`}
                >
                  <span className="store-chip__icon" aria-hidden="true">{s.emoji}</span>
                  <span className="store-chip__name">{s.name}</span>
                  <svg className="store-chip__arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M7 17L17 7M17 7H7M17 7v10" />
                  </svg>
                </a>
              </li>
            ))}
          </ul>

          <p className="stores__note">
            Uskoro: još više dućana i kategorizacija vina po podrumima.
          </p>
        </div>
      </section>
    </>
  )
}
