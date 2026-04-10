import {
  AlertTriangle,
  ImageOff,
  TrendingDown,
  ArrowDownRight,
  HelpCircle,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  formatKillTier,
  formatKillAction,
  formatUSD,
  formatPercent,
  formatROAS,
  calculateMoneySaved,
} from "@/lib/formatters"
import type { KilledCampaign, CampaignFitnessScore } from "@/types"
import { MetricTooltip } from "./MetricTooltip"

const TIER_ICONS: Record<string, React.ElementType> = {
  AlertTriangle,
  ImageOff,
  TrendingDown,
  ArrowDownRight,
  HelpCircle,
}

interface KilledCampaignCardProps {
  killed: KilledCampaign
  fitnessScore: CampaignFitnessScore | undefined
  getName: (id: string) => string
}

export default function KilledCampaignCard({
  killed,
  fitnessScore,
  getName,
}: KilledCampaignCardProps) {
  const tier = formatKillTier(killed.tier)
  const TierIcon = TIER_ICONS[tier.iconName] ?? HelpCircle

  return (
    <Card className="border-red-200 bg-red-50/30">
      <CardContent className="pt-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <p className="font-medium text-sm">
            {getName(killed.campaign_id)}
          </p>
          <Badge variant="destructive" className="shrink-0 text-xs">
            <TierIcon className="h-3 w-3 mr-1" />
            {tier.label}
          </Badge>
        </div>

        <p className="text-sm text-muted-foreground">{tier.description}</p>
        <p className="text-sm text-muted-foreground italic">{killed.reason}</p>

        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {formatKillAction(killed.action)}
          </span>
          <span className="font-medium text-red-600">
            ~{formatUSD(calculateMoneySaved([killed]))} ahorrados/semana
          </span>
        </div>

        {fitnessScore && (
          <div className="flex gap-4 pt-2 border-t text-xs text-muted-foreground">
            <MetricTooltip
              label="CTR"
              value={formatPercent(fitnessScore.raw_scores?.ctr)}
              tooltip="Tasa de clics: de cada 100 personas que ven tu anuncio, este porcentaje hace clic"
            />
            <MetricTooltip
              label="CPC"
              value={formatUSD(fitnessScore.raw_scores?.cpc ?? 0)}
              tooltip="Costo por clic: cada clic en tu anuncio cuesta este valor"
            />
            <MetricTooltip
              label="ROAS"
              value={formatROAS(fitnessScore.raw_scores?.roas).text}
              tooltip="Retorno sobre inversión publicitaria: por cada peso invertido, cuánto ganas de vuelta"
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
