import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import {
  Clock,
  BarChart2,
  CheckCircle,
  HelpCircle,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  formatClassification,
  formatFitnessScore,
  formatROAS,
  formatPercent,
  formatUSD,
} from "@/lib/formatters"
import { MetricTooltip } from "./MetricTooltip"
import type {
  CampaignFitnessScore,
  KilledCampaign,
  DuplicatedCampaign,
} from "@/types"

const CLASS_ICONS: Record<string, React.ElementType> = {
  Clock,
  BarChart2,
  CheckCircle,
  HelpCircle,
}

interface FitnessRankingTableProps {
  fitnessScores: Record<string, CampaignFitnessScore>
  kills: KilledCampaign[]
  duplications: DuplicatedCampaign[]
  getName: (id: string) => string
}

type SortKey = "score" | "roas" | "ctr" | "cpc"

export default function FitnessRankingTable({
  fitnessScores,
  kills,
  duplications,
  getName,
}: FitnessRankingTableProps) {
  const [sortBy, setSortBy] = useState<SortKey>("score")

  const killSet = useMemo(
    () => new Set(kills.map((k) => k.campaign_id)),
    [kills]
  )
  const dupSet = useMemo(
    () => new Set(duplications.map((d) => d.parent_id)),
    [duplications]
  )

  const rows = useMemo(() => {
    const entries = Object.entries(fitnessScores).map(([id, s]) => ({
      id,
      score: s,
    }))

    entries.sort((a, b) => {
      const aVal = getSortValue(a.score, sortBy)
      const bVal = getSortValue(b.score, sortBy)
      return bVal - aVal
    })

    return entries
  }, [fitnessScores, sortBy])

  if (rows.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="pb-3 pr-2 font-medium text-muted-foreground w-8">
              #
            </th>
            <th className="pb-3 pr-2 font-medium text-muted-foreground min-w-[140px]">
              Campaña
            </th>
            <th className="pb-3 pr-2 font-medium text-muted-foreground">
              Estado
            </th>
            <th
              className="pb-3 pr-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground min-w-[140px]"
              onClick={() => setSortBy("score")}
            >
              Puntuación {sortBy === "score" && "↓"}
            </th>
            <th
              className="pb-3 pr-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => setSortBy("roas")}
            >
              ROAS {sortBy === "roas" && "↓"}
            </th>
            <th
              className="pb-3 pr-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => setSortBy("ctr")}
            >
              CTR {sortBy === "ctr" && "↓"}
            </th>
            <th
              className="pb-3 pr-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground"
              onClick={() => setSortBy("cpc")}
            >
              CPC {sortBy === "cpc" && "↓"}
            </th>
            <th className="pb-3 font-medium text-muted-foreground">Acción</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map(({ id, score }, i) => {
            const cls = formatClassification(score.classification)
            const ClsIcon = CLASS_ICONS[cls.iconName] ?? HelpCircle
            const fitness = formatFitnessScore(score.final_score)
            const isImmature = score.classification === "immature"
            const isKilled = killSet.has(id)
            const isDuplicated = dupSet.has(id)

            return (
              <tr key={id} className={cn(isKilled && "opacity-60")}>
                <td className="py-3 pr-2 text-muted-foreground">{i + 1}</td>
                <td className="py-3 pr-2">
                  <span className="font-medium" title={getName(id)}>
                    {truncate(getName(id), 35)}
                  </span>
                </td>
                <td className="py-3 pr-2">
                  <Badge variant="secondary" className={cn("text-xs", cls.color)}>
                    <ClsIcon className="h-3 w-3 mr-1" />
                    {cls.label}
                  </Badge>
                </td>
                <td className="py-3 pr-2">
                  {isImmature ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-20 rounded-full bg-muted overflow-hidden">
                        <div
                          className={cn("h-full rounded-full", fitness.bgColor)}
                          style={{
                            width: `${Math.min(100, score.final_score * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground">
                        ({score.final_score.toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 })})
                      </span>
                    </div>
                  )}
                </td>
                <td className="py-3 pr-2">
                  <MetricTooltip
                    label=""
                    value={formatROAS(score.raw_scores?.roas).text}
                    tooltip="Retorno sobre inversión publicitaria"
                  />
                </td>
                <td className="py-3 pr-2">
                  <MetricTooltip
                    label=""
                    value={score.raw_scores?.ctr != null ? formatPercent(score.raw_scores.ctr) : "—"}
                    tooltip="Tasa de clics"
                  />
                </td>
                <td className="py-3 pr-2">
                  <MetricTooltip
                    label=""
                    value={score.raw_scores?.cpc != null ? formatUSD(score.raw_scores.cpc) : "—"}
                    tooltip="Costo por clic"
                  />
                </td>
                <td className="py-3">
                  {isKilled ? (
                    <span className="text-red-600 text-xs font-medium">
                      🛑 Pausada
                    </span>
                  ) : isDuplicated ? (
                    <span className="text-green-600 text-xs font-medium">
                      🧬 Duplicada
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 3) + "..." : s
}

function getSortValue(score: CampaignFitnessScore, key: SortKey): number {
  switch (key) {
    case "score":
      return score.final_score
    case "roas":
      return score.raw_scores?.roas ?? 0
    case "ctr":
      return score.raw_scores?.ctr ?? 0
    case "cpc":
      return -(score.raw_scores?.cpc ?? Infinity) // lower is better
    default:
      return 0
  }
}
