import './ErrorMessage.css'

interface ErrorMessageProps {
  message?: string
  onRetry?: () => void
}

export default function ErrorMessage({
  message = 'Nismo mogli učitati podatke.',
  onRetry,
}: ErrorMessageProps) {
  return (
    <div className="error-msg" role="alert">
      <span className="error-msg__icon" aria-hidden="true">⚠️</span>
      <p className="error-msg__text">{message}</p>
      {onRetry && (
        <button className="btn btn--ghost error-msg__retry" onClick={onRetry} type="button">
          Pokušaj ponovo
        </button>
      )}
    </div>
  )
}
