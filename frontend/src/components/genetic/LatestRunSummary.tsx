import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  formatTimeAgo,
  formatUSD,
  formatROAS,
  calculateMoneySaved,
} from "@/lib/formatters"
import type { OptimizationRun, GeneticConfig } from "@/types"

interface LatestRunSummaryProps {
  run: OptimizationRun
  config: GeneticConfig | undefined
  getName: (id: string) => string
  onViewDetails?: () => void
}

export default function LatestRunSummary({
  run,
  getName,
  onViewDetails,
}: LatestRunSummaryProps) {
  // Find best campaign by final_score
  let bestId = ""
  let bestScore = -1
  for (const [id, score] of Object.entries(run.fitness_scores ?? {})) {
    if (score.final_score > bestScore) {
      bestScore = score.final_score
      bestId = id
    }
  }
  const bestRoas = bestId
    ? run.fitness_scores[bestId]?.raw_scores?.roas ?? 0
    : 0

  const killed = run.campaigns_killed ?? []
  const duplicated = run.campaigns_duplicated ?? []
  const moneySaved = calculateMoneySaved(killed)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Última optimización</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          {formatTimeAgo(run.ran_at)} &middot; Generación #{run.generation_number}
        </p>

        <div className="space-y-2">
          <p>
            ✅ <strong>{run.campaigns_evaluated}</strong> campañas evaluadas
          </p>

          {killed.length > 0 ? (
            <p>
              🛑 <strong>{killed.length}</strong> campañas pausadas (ahorraste
              ~{formatUSD(moneySaved)} esta semana)
            </p>
          ) : (
            <p>✅ Todas tus campañas están rindiendo bien</p>
          )}

          {duplicated.length > 0 ? (
            <p>
              🧬 <strong>{duplicated.length}</strong> nuevas variantes creadas
            </p>
          ) : (
            <p>
              💤 No hubo campañas con rendimiento suficiente para replicar
            </p>
          )}

          {bestId && bestRoas > 0 && (
            <p>
              🏆 Tu mejor campaña: &quot;{getName(bestId)}&quot; con{" "}
              <span className={formatROAS(bestRoas).color}>
                ROAS {formatROAS(bestRoas).text}
              </span>
            </p>
          )}
        </div>

        {onViewDetails && (
          <button
            type="button"
            onClick={onViewDetails}
            className="text-primary text-sm hover:underline mt-2"
          >
            Ver detalles completos &rarr;
          </button>
        )}
      </CardContent>
    </Card>
  )
}
