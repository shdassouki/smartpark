// Persistent, non-dismissible banner clarifying that availability values are
// simulated for the prototype and are not live parking data.

export function DisclaimerBanner() {
  return (
    <div className="disclaimer-banner" role="note">
      Availability estimates are simulated for this prototype and are not live
      parking data.
    </div>
  )
}
