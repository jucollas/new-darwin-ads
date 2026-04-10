import type { OptimizationRun, GeneticConfig } from "@/types"
import KilledCampaignCard from "./KilledCampaignCard"
import DuplicatedCampaignCard from "./DuplicatedCampaignCard"
import FitnessRankingTable from "./FitnessRankingTable"

interface RunDetailProps {
  run: OptimizationRun
  config: GeneticConfig | undefined
  getName: (id: string) => string
}

export default function RunDetail({ run, getName }: RunDetailProps) {
  const killed = run.campaigns_killed ?? []
  const duplicated = run.campaigns_duplicated ?? []
  const scores = run.fitness_scores ?? {}

  return (
    <div className="space-y-6 pt-4">
      {/* Killed Campaigns */}
      <div>
        <h4 className="text-sm font-semibold mb-3">Campañas pausadas</h4>
        {killed.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {killed.map((k) => (
              <KilledCampaignCard
                key={k.campaign_id}
                killed={k}
                fitnessScore={scores[k.campaign_id]}
                getName={getName}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            ✅ No se pausó ninguna campaña en esta generación
          </p>
        )}
      </div>

      {/* Duplicated Campaigns */}
      <div>
        <h4 className="text-sm font-semibold mb-3">Nuevas variantes</h4>
        {duplicated.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {duplicated.map((d) => (
              <DuplicatedCampaignCard
                key={d.new_campaign_id}
                duplicated={d}
                parentFitness={scores[d.parent_id]}
                getName={getName}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            💤 No se crearon variantes en esta generación
          </p>
        )}
      </div>

      {/* Fitness Ranking */}
      {Object.keys(scores).length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-3">
            Ranking de campañas
          </h4>
          <FitnessRankingTable
            fitnessScores={scores}
            kills={killed}
            duplications={duplicated}
            getName={getName}
          />
        </div>
      )}
    </div>
  )
}
