import { formatFitnessScore } from "@/lib/formatters"
import type { CampaignFitnessScore } from "@/types"

interface PortfolioSummaryBarProps {
  fitnessScores: Record<string, CampaignFitnessScore>
}

export default function PortfolioSummaryBar({
  fitnessScores,
}: PortfolioSummaryBarProps) {
  const scores = Object.values(fitnessScores ?? {})
  const total = scores.length
  const mature = scores.filter((s) => s.classification === "mature").length
  const early = scores.filter((s) => s.classification === "early_stage").length
  const immature = scores.filter((s) => s.classification === "immature").length

  const nonImmature = scores.filter((s) => s.classification !== "immature")
  const avgScore =
    nonImmature.length > 0
      ? nonImmature.reduce((sum, s) => sum + s.final_score, 0) /
        nonImmature.length
      : 0

  const avgFormatted = formatFitnessScore(avgScore)

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 p-4 rounded-lg bg-muted/50 text-sm">
      <span>
        📊 <strong>{total}</strong> campañas
      </span>
      <span className="text-muted-foreground">&middot;</span>
      <span>
        <strong>{mature}</strong> evaluadas
      </span>
      <span className="text-muted-foreground">&middot;</span>
      <span>
        <strong>{early}</strong> en evaluación
      </span>
      <span className="text-muted-foreground">&middot;</span>
      <span>
        <strong>{immature}</strong> recopilando datos
      </span>
      {nonImmature.length > 0 && (
        <>
          <span className="text-muted-foreground">&middot;</span>
          <span>
            Puntuación promedio:{" "}
            <strong className={avgFormatted.color}>
              {avgScore.toLocaleString("es-CO", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{" "}
              ({avgFormatted.label})
            </strong>
          </span>
        </>
      )}
    </div>
  )
}
