// SmartPark input form: destination building, class/event start time, and
// permit type. Validates that all three fields are populated before calling
// the submit callback. Building and permit options are discrete selects.
//
// Visual/layout refinement only — the validation, submit logic, options,
// and field values are unchanged.

import { useState } from 'react'
import { BUILDING_OPTIONS, PERMIT_OPTIONS } from '../utils/options'
import type { RecommendationRequest } from '../utils/api'
import { DisclaimerBanner } from './DisclaimerBanner'
import { PinIcon, ClockIcon, ShieldIcon, ChevronIcon, ArrowIcon } from './icons'

interface InputFormProps {
  onSubmit: (request: RecommendationRequest) => void
  disabled: boolean
}

export function InputForm({ onSubmit, disabled }: InputFormProps) {
  const [buildingId, setBuildingId] = useState('')
  const [startTime, setStartTime] = useState('')
  const [permitType, setPermitType] = useState('')
  const [errors, setErrors] = useState<string[]>([])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    const missing: string[] = []
    if (!buildingId) missing.push('destination building')
    if (!startTime) missing.push('class/event start time')
    if (!permitType) missing.push('permit type')

    if (missing.length > 0) {
      setErrors(missing)
      return
    }

    setErrors([])
    onSubmit({
      building_id: buildingId,
      start_time: startTime,
      permit_type: permitType,
    })
  }

  return (
    <>
      {/* White-on-navy hero / landing block */}
      <section className="hero">
        <div className="brand-header">
          <span className="brand-mark">SP</span>
          <span className="brand-name">SmartPark</span>
        </div>
        <h1 className="hero-headline">Campus parking, figured out.</h1>
        <p className="hero-subtitle">
          Find the best lot for your class based on predicted availability,
          walking distance, and your permit.
        </p>
      </section>

      <form className="input-form card" onSubmit={handleSubmit} noValidate>
        <h2 className="section-heading">Where are you headed?</h2>

        {/* Destination — full-width primary control */}
        <div className="field tile">
          <label htmlFor="building">
            <PinIcon className="field-icon" />
            Destination building
          </label>
          <div className="select-wrap">
            <select
              id="building"
              value={buildingId}
              onChange={(e) => setBuildingId(e.target.value)}
              disabled={disabled}
            >
              <option value="">Select a building…</option>
              {BUILDING_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <ChevronIcon className="select-chevron" />
          </div>
        </div>

        {/* Time + permit — two compact app-style controls side by side */}
        <div className="field-row">
          <div className="field tile">
            <label htmlFor="start-time">
              <ClockIcon className="field-icon" />
              Class/event time
            </label>
            <input
              id="start-time"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              disabled={disabled}
            />
          </div>

          <div className="field tile">
            <label htmlFor="permit">
              <ShieldIcon className="field-icon" />
              Permit type
            </label>
            <div className="select-wrap">
              <select
                id="permit"
                value={permitType}
                onChange={(e) => setPermitType(e.target.value)}
                disabled={disabled}
              >
                <option value="">Select…</option>
                {PERMIT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronIcon className="select-chevron" />
            </div>
          </div>
        </div>

        {errors.length > 0 && (
          <div className="form-errors" role="alert">
            Please fill in: {errors.join(', ')}.
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={disabled}>
          {disabled ? 'Finding your best lot…' : 'Find My Best Lot'}
          {!disabled && <ArrowIcon className="cta-arrow" />}
        </button>

        <DisclaimerBanner />
      </form>
    </>
  )
}
