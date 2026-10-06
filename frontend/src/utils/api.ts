// API helper for the SmartPark recommendation endpoint.
// The endpoint URL comes from the VITE_API_URL environment variable
// (see .env.example). The API URL is a public endpoint, not a secret.

export interface RecommendationRequest {
  building_id: string
  start_time: string
  permit_type: string
}

// The winning lot. Mirrors the backend "recommendation" object.
// Note: the internal composite score is intentionally not exposed by the API.
export interface Recommendation {
  lot_name: string
  availability_percentage: number
  walking_time_minutes: number
  permit_eligible: boolean
  arrival_time: string
  explanation: string
  simulated_data: boolean
}

// A runner-up alternative lot. Mirrors each entry in the backend
// "alternatives" array.
export interface Alternative {
  lot_name: string
  availability_percentage: number
  walking_time_minutes: number
  permit_eligible: boolean
}

// The full POST /recommend success response.
export interface RecommendationResponse {
  recommendation: Recommendation
  alternatives: Alternative[]
}

// Thrown when the API returns a non-2xx response. errorType distinguishes
// the "no eligible lots" case (404) from any other failure, so the UI can
// show the appropriate message.
export class ApiError extends Error {
  errorType: 'no_eligible_lots' | 'generic'
  constructor(message: string, errorType: 'no_eligible_lots' | 'generic') {
    super(message)
    this.name = 'ApiError'
    this.errorType = errorType
  }
}

const API_URL = import.meta.env.VITE_API_URL as string | undefined

export async function fetchRecommendation(
  request: RecommendationRequest,
): Promise<RecommendationResponse> {
  if (!API_URL) {
    throw new ApiError(
      'API URL is not configured. Set VITE_API_URL in your .env.local file.',
      'generic',
    )
  }

  let response: Response
  try {
    response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
  } catch {
    // Network error, DNS failure, CORS block, etc.
    throw new ApiError(
      'Could not reach the SmartPark service. Please check your connection and try again.',
      'generic',
    )
  }

  if (response.ok) {
    return (await response.json()) as RecommendationResponse
  }

  // Non-2xx: try to read the error body for a message.
  let message = 'Something went wrong. Please try again.'
  try {
    const body = await response.json()
    if (body && typeof body.message === 'string') {
      message = body.message
    }
  } catch {
    // Ignore body parse errors; fall back to the default message.
  }

  const errorType = response.status === 404 ? 'no_eligible_lots' : 'generic'
  throw new ApiError(message, errorType)
}
