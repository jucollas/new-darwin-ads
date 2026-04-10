import ImpactHeroCards from "./ImpactHeroCards"
import PerformanceChart from "./PerformanceChart"
import LatestRunSummary from "./LatestRunSummary"
import TopPerformersPodium from "./TopPerformersPodium"
import { calculatePortfolioROASOverTime } from "@/lib/formatters"
import type {
  OptimizationRun,
  GeneticConfig,
  MetricsSummary,
  TopPerformer,
} from "@/types"

interface ImpactSummaryTabProps {
  runs: OptimizationRun[]
  config: GeneticConfig | undefined
  metrics: MetricsSummary | undefined
  topPerformers: TopPerformer[]
  getName: (id: string) => string
  onSwitchToHistory?: () => void
}

export default function ImpactSummaryTab({
  runs,
  config,
  metrics,
  topPerformers,
  getName,
  onSwitchToHistory,
}: ImpactSummaryTabProps) {
  const chartData = calculatePortfolioROASOverTime(runs)
  const latestRun = runs[0]

  return (
    <div className="space-y-6">
      <ImpactHeroCards runs={runs} config={config} metrics={metrics} />

      <PerformanceChart data={chartData} />

      {latestRun && (
        <LatestRunSummary
          run={latestRun}
          config={config}
          getName={getName}
          onViewDetails={onSwitchToHistory}
        />
      )}

      <TopPerformersPodium
        performers={topPerformers}
        getName={getName}
      />
    </div>
  )
}
