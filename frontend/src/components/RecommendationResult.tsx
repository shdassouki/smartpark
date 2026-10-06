// Displays a successful recommendation as ONE visual group: a dominant
// BEST MATCH card with the two alternatives attached directly beneath it,
// followed by a separate "Why this lot?" explanation card.
// Visual/layout refinement only — data/props are unchanged.

import type { Recommendation, Alternative } from '../utils/api'
import { DisclaimerBanner } from './DisclaimerBanner'
import {
  AvailabilityIcon,
  WalkIcon,
  ClockIcon,
  CheckIcon,
  CrossIcon,
} from './icons'

interface RecommendationResultProps {
  recommendation: Recommendation
  alternatives: Alternative[]
  onReset: () => void
}

export function RecommendationResult({
  recommendation,
  alternatives,
  onReset,
}: RecommendationResultProps) {
  const {
    lot_name,
    availability_percentage,
    walking_time_minutes,
    permit_eligible,
    arrival_time,
    explanation,
  } = recommendation

  return (
    <div className="recommendation-result">
      <header className="brand-header on-light">
        <span className="brand-mark">SP</span>
        <span className="brand-name">SmartPark</span>
      </header>

      {/* The winner + alternatives form one bound recommendation group. */}
      <section className="recommendation-group" aria-label="Parking recommendation">
        <div className="best-card">
          <span className="best-badge">
            <CheckIcon className="badge-icon" />
            Best match
          </span>
          <h1 className="best-lot-name">{lot_name}</h1>

          <div className="arrive-by">
            <span className="arrive-label">
              <ClockIcon className="arrive-icon" />
              Arrive by
            </span>
            <span className="arrive-time">{arrival_time}</span>
            <span className="arrive-note">
              to make it to class on time, including time to find a spot
            </span>
          </div>

          <div className="stat-row">
            <div className="stat">
              <AvailabilityIcon className="stat-icon" />
              <div className="stat-value">{availability_percentage}%</div>
              <div className="stat-label">Predicted availability</div>
            </div>
            <div className="stat">
              <WalkIcon className="stat-icon" />
              <div className="stat-value">{walking_time_minutes} min</div>
              <div className="stat-label">Walk to destination</div>
            </div>
          </div>

          <span className={`permit-pill ${permit_eligible ? 'valid' : 'invalid'}`}>
            {permit_eligible ? <CheckIcon /> : <CrossIcon />}
            {permit_eligible ? 'Permit valid for this lot' : 'Permit not valid'}
          </span>
        </div>

        {/* Alternatives attached directly beneath the winner. */}
        {alternatives.length > 0 && (
          <div className="alt-grid">
            {alternatives.map((alt) => (
              <div className="alt-card" key={alt.lot_name}>
                <span className="alt-name">{alt.lot_name}</span>
                <span className="alt-stat">
                  <AvailabilityIcon className="alt-icon" />
                  <span className="alt-availability">
                    {alt.availability_percentage}%
                  </span>
                </span>
                <span className="alt-stat">
                  <WalkIcon className="alt-icon" />
                  {alt.walking_time_minutes} min
                </span>
                <span
                  className={`permit-tag ${alt.permit_eligible ? 'valid' : 'invalid'}`}
                >
                  {alt.permit_eligible ? <CheckIcon /> : <CrossIcon />}
                  {alt.permit_eligible ? 'Permit' : 'No permit'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Why this lot — separate card below the recommendation group. */}
      <section className="why-card">
        <h2>Why this lot?</h2>
        <p className="explanation">{explanation}</p>
      </section>

      <button type="button" className="btn-secondary" onClick={onReset}>
        Search again
      </button>

      <DisclaimerBanner />
    </div>
  )
}
