// Displays an error. Distinguishes:
//   - no_eligible_lots:   permit matches no lots (suggest checking permit)
//   - no_availability_data: eligible lots exist but no simulated availability
//                           for the selected time (suggest a supported time)
//   - generic:            any other failure
// Presentation only — the message text comes from the API.

import type { ErrorType } from '../utils/api'

interface ErrorStateProps {
  errorType: ErrorType
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
        ) : errorType === 'no_availability_data' ? (
          <>
            <h1>Try a different time</h1>
            <p>{message}</p>
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
