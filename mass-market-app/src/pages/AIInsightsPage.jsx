import CarrierAIInsights from '../components/CarrierAIInsights'
import { useVisibleCarriers } from '../hooks/useHiddenCarrier'
import { DOMESTIC_LABELS, carrierLabel } from '../data/carrierLabels'

export default function AIInsightsPage() {
  const allDomestic = Object.keys(DOMESTIC_LABELS)
  const carriers = useVisibleCarriers(allDomestic)

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-moca-text">AI Insights</h1>
        <p className="text-xs text-moca-muted mt-0.5">תובנות תחרותיות מבוססות Claude עבור כל ספק. לחץ "דוח AI" לפתיחת ניתוח לכל ספק.</p>
      </div>

      <div className="space-y-3">
        {carriers.map(c => (
          <div key={c} className="bg-white border border-moca-border/60 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-moca-text">{carrierLabel(c)}</span>
            </div>
            <CarrierAIInsights carrierId={c} inline />
          </div>
        ))}
      </div>
    </div>
  )
}
