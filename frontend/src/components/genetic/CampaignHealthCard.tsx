import { Link } from "react-router-dom"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Clock,
  BarChart2,
  CheckCircle,
  HelpCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  formatClassification,
  formatFitnessScore,
  formatROAS,
  formatPercent,
  formatUSD,
} from "@/lib/formatters"
import { MetricTooltip } from "./MetricTooltip"
import type { CampaignFitnessScore, GeneticConfig } from "@/types"

const CLASS_ICONS: Record<string, React.ElementType> = {
  Clock,
  BarChart2,
  CheckCircle,
  HelpCircle,
}

interface CampaignHealthCardProps {
  campaignId: string
  fitness: CampaignFitnessScore | undefined
  config: GeneticConfig | undefined
  getName: (id: string) => string
  wasKilled: boolean
  wasDuplicated: boolean
}

export default function CampaignHealthCard({
  campaignId,
  fitness,
  config,
  getName,
  wasKilled,
  wasDuplicated,
}: CampaignHealthCardProps) {
  if (!fitness) return null

  const cls = formatClassification(fitness.classification)
  const ClsIcon = CLASS_ICONS[cls.iconName] ?? HelpCircle
  const isImmature = fitness.classification === "immature"

  if (isImmature) {
    return (
      <ImmatureCard
        campaignId={campaignId}
        fitness={fitness}
        config={config}
        getName={getName}
      />
    )
  }

  const fitnessFormatted = formatFitnessScore(fitness.final_score)
  const roas = formatROAS(fitness.raw_scores?.roas)

  return (
    <Card
      className={cn(
        "relative overflow-hidden",
        wasKilled && "border-red-300",
        wasDuplicated && "border-green-300"
      )}
    >
      {wasKilled && (
        <div className="absolute inset-0 bg-red-500/5 pointer-events-none z-10" />
      )}
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <p className="font-medium text-sm leading-tight">
            {getName(campaignId)}
          </p>
          <Badge variant="secondary" className={cn("text-xs shrink-0", cls.color)}>
            <ClsIcon className="h-3 w-3 mr-1" />
            {cls.label}
          </Badge>
        </div>

        {wasKilled && (
          <Badge variant="destructive" className="text-xs">
            🛑 Pausada por el optimizador
          </Badge>
        )}
        {wasDuplicated && (
          <Badge className="text-xs bg-green-100 text-green-700 hover:bg-green-200">
            🧬 Replicada
          </Badge>
        )}

        {/* Score bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Puntuación</span>
            <span className={cn("font-medium", fitnessFormatted.color)}>
              {fitnessFormatted.label}
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
            <div
              className={cn("h-full rounded-full", fitnessFormatted.bgColor)}
              style={{
                width: `${Math.min(100, fitness.final_score * 100)}%`,
              }}
            />
          </div>
        </div>

        {/* Metrics row */}
        <div className="flex gap-4 text-xs pt-1">
          <MetricTooltip
            label="ROAS"
            value={roas.text}
            tooltip="Retorno sobre inversión publicitaria: por cada peso que inviertes en anuncios, cuánto ganas de vuelta"
          />
          <MetricTooltip
            label="CTR"
            value={fitness.raw_scores?.ctr != null ? formatPercent(fitness.raw_scores.ctr) : "—"}
            tooltip="Tasa de clics: de cada 100 personas que ven tu anuncio, este porcentaje hace clic"
          />
          <MetricTooltip
            label="CPC"
            value={fitness.raw_scores?.cpc != null ? formatUSD(fitness.raw_scores.cpc) : "—"}
            tooltip="Costo por clic: cada clic en tu anuncio cuesta este valor"
          />
        </div>

        {/* Confidence */}
        <div className="text-xs text-muted-foreground">
          Confianza: {Math.min(100, Math.round(fitness.confidence_factor * 100))}%
        </div>

        <Link
          to={`/campaigns/${campaignId}`}
          className="text-xs text-primary hover:underline block pt-1"
        >
          Ver campaña &rarr;
        </Link>
      </CardContent>
    </Card>
  )
}

function ImmatureCard({
  campaignId,
  fitness,
  config,
  getName,
}: {
  campaignId: string
  fitness: CampaignFitnessScore
  config: GeneticConfig | undefined
  getName: (id: string) => string
}) {
  const impressions = fitness.raw_scores?.impressions ?? 0
  const minImpressions = config?.min_impressions_to_evaluate ?? 100
  const impressionPct = Math.min(100, (impressions / minImpressions) * 100)

  const confidencePct = Math.min(100, fitness.confidence_factor * 100)

  return (
    <Card className="border-dashed">
      <CardContent className="pt-4 space-y-3">
        <p className="font-medium text-sm leading-tight">
          {getName(campaignId)}
        </p>

        <p className="text-sm text-muted-foreground flex items-center gap-1.5">
          <Clock className="h-4 w-4" />
          Recopilando datos...
        </p>

        {/* Impressions progress */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Impresiones</span>
            <span className="text-muted-foreground">
              {Math.round(impressions).toLocaleString("es-CO")} / {minImpressions.toLocaleString("es-CO")}
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-400"
              style={{ width: `${impressionPct}%` }}
            />
          </div>
        </div>

        {/* Overall progress */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Progreso general</span>
            <span className="text-muted-foreground">
              {Math.round(confidencePct)}%
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-400"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>

        <p className="text-xs text-muted-foreground italic">
          El sistema necesita más datos para evaluar esta campaña.
        </p>
      </CardContent>
    </Card>
  )
}
