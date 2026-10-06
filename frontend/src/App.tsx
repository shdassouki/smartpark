// SmartPark root component. Manages the top-level view state and wires the
// InputForm to the deployed /recommend API.

import { useState } from 'react'
import './App.css'
import { InputForm } from './components/InputForm'
import { RecommendationResult } from './components/RecommendationResult'
import { ErrorState } from './components/ErrorState'
import {
  fetchRecommendation,
  ApiError,
  type RecommendationResponse,
  type RecommendationRequest,
} from './utils/api'

type View =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; response: RecommendationResponse }
  | { status: 'error'; errorType: 'no_eligible_lots' | 'generic'; message: string }

function App() {
  const [view, setView] = useState<View>({ status: 'idle' })

  async function handleSubmit(request: RecommendationRequest) {
    setView({ status: 'loading' })
    try {
      const response = await fetchRecommendation(request)
      setView({ status: 'success', response })
    } catch (err) {
      if (err instanceof ApiError) {
        setView({ status: 'error', errorType: err.errorType, message: err.message })
      } else {
        setView({
          status: 'error',
          errorType: 'generic',
          message: 'An unexpected error occurred. Please try again.',
        })
      }
    }
  }

  function handleReset() {
    setView({ status: 'idle' })
  }

  return (
    <>
      {/* Fixed decorative background layers (glows + optional campus image).
          Purely presentational; sit behind all content and never capture
          pointer events. */}
      <div className="bg-layer" aria-hidden="true">
        <div className="bg-glow bg-glow-blue" />
        <div className="bg-glow bg-glow-violet" />
        <div className="bg-glow bg-glow-low" />
        <div className="bg-campus" />
      </div>

      <main className="app">
        {(view.status === 'idle' || view.status === 'loading') && (
          <InputForm onSubmit={handleSubmit} disabled={view.status === 'loading'} />
        )}

        {view.status === 'success' && (
          <RecommendationResult
            recommendation={view.response.recommendation}
            alternatives={view.response.alternatives}
            onReset={handleReset}
          />
        )}

        {view.status === 'error' && (
          <ErrorState
            errorType={view.errorType}
            message={view.message}
            onReset={handleReset}
          />
        )}
      </main>
    </>
  )
}

export default App
