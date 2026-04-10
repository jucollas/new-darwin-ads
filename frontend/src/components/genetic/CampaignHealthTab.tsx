import { useMemo } from "react"
import { Link } from "react-router-dom"
import { Dna } from "lucide-react"
import PortfolioSummaryBar from "./PortfolioSummaryBar"
import CampaignHealthCard from "./CampaignHealthCard"
import type { OptimizationRun, GeneticConfig } from "@/types"

interface CampaignHealthTabProps {
  runs: OptimizationRun[]
  config: GeneticConfig | undefined
  getName: (id: string) => string
}

export default function CampaignHealthTab({
  runs,
  config,
  getName,
}: CampaignHealthTabProps) {
  const latestRun = runs[0]

  const { fitnessScores, killSet, dupSet, sortedIds } = useMemo(() => {
    if (!latestRun) {
      return {
        fitnessScores: {},
        killSet: new Set<string>(),
        dupSet: new Set<string>(),
        sortedIds: [] as string[],
      }
    }

    const scores = latestRun.fitness_scores ?? {}
    const kills = new Set(
      (latestRun.campaigns_killed ?? []).map((k) => k.campaign_id)
    )
    const dups = new Set(
      (latestRun.campaigns_duplicated ?? []).map((d) => d.parent_id)
    )

    // Sort: mature desc, early_stage desc, immature, killed last
    const ids = Object.keys(scores)
    ids.sort((a, b) => {
      const sa = scores[a]
      const sb = scores[b]
      const orderA = classificationOrder(sa.classification, kills.has(a))
      const orderB = classificationOrder(sb.classification, kills.has(b))
      if (orderA !== orderB) return orderA - orderB
      return sb.final_score - sa.final_score
    })

    return { fitnessScores: scores, killSet: kills, dupSet: dups, sortedIds: ids }
  }, [latestRun])

  if (!latestRun) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
        <Dna className="h-16 w-16 text-muted-foreground/50" />
        <p className="text-muted-foreground">
          Aún no hay datos de optimización. El sistema analizará tus campañas automáticamente.
        </p>
        <Link to="/campaigns" className="text-sm text-primary hover:underline">
          Ir a mis campañas &rarr;
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PortfolioSummaryBar fitnessScores={fitnessScores} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sortedIds.map((id) => (
          <CampaignHealthCard
            key={id}
            campaignId={id}
            fitness={fitnessScores[id]}
            config={config}
            getName={getName}
            wasKilled={killSet.has(id)}
            wasDuplicated={dupSet.has(id)}
          />
        ))}
      </div>
    </div>
  )
}

function classificationOrder(
  classification: string,
  isKilled: boolean
): number {
  if (isKilled) return 4
  switch (classification) {
    case "mature":
      return 1
    case "early_stage":
      return 2
    case "immature":
      return 3
    default:
      return 5
  }
}
