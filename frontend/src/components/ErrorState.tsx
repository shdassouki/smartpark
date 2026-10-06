// Displays an error. Distinguishes the "no eligible lots" case (suggest
// checking the permit type) from any other error (generic message + retry).
// Visual redesign only — behavior unchanged.

interface ErrorStateProps {
  errorType: 'no_eligible_lots' | 'generic'
  message: string
  onReset: () => void
}

export function ErrorState({ errorType, message, onReset }: ErrorStateProps) {
  return (
    <>
      <header className="brand-header on-light">
        <span className="brand-mark">SP</span>
        <span className="brand-name">SmartPark</span>
      </header>

      <div className="error-state card" role="alert">
        {errorType === 'no_eligible_lots' ? (
          <>
            <h1>No lots available</h1>
            <p>{message}</p>
            <p>Double-check that you selected the right permit type.</p>
          </>
        ) : (
          <>
            <h1>Something went wrong</h1>
            <p>{message}</p>
          </>
        )}

        <button type="button" className="btn-secondary" onClick={onReset}>
          Back to form
        </button>
      </div>
    </>
  )
}
