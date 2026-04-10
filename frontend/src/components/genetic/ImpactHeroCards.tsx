import { MessageSquare, ShieldCheck, TrendingUp, Target } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { formatUSD, formatROAS, calculateMoneySavedFromRuns } from "@/lib/formatters"
import type { OptimizationRun, MetricsSummary, GeneticConfig } from "@/types"
import { cn } from "@/lib/utils"

interface ImpactHeroCardsProps {
  runs: OptimizationRun[]
  config: GeneticConfig | undefined
  metrics: MetricsSummary | undefined
}

export default function ImpactHeroCards({
  runs,
  config,
  metrics,
}: ImpactHeroCardsProps) {
  const totalConversions = metrics?.total_conversions ?? 0
  const moneySaved = calculateMoneySavedFromRuns(runs)

  // Deduplicate killed campaign IDs across runs
  const killedIds = new Set<string>()
  for (const run of runs) {
    for (const k of run.campaigns_killed ?? []) {
      killedIds.add(k.campaign_id)
    }
  }
  const totalKilled = killedIds.size

  const avgRoas = metrics?.average_roas ?? metrics?.avg_roas ?? 0
  const roasFormatted = formatROAS(avgRoas)

  const totalSpend = metrics?.total_spend_cents ?? 0
  const convs = metrics?.total_conversions ?? 0
  const costPerConv = convs > 0 ? totalSpend / convs : 0
  const targetCpa = config?.target_cpa_cents ?? 0

  const cpaColor =
    costPerConv === 0
      ? "text-muted-foreground"
      : costPerConv <= targetCpa
        ? "text-emerald-600"
        : costPerConv <= targetCpa * 1.2
          ? "text-yellow-600"
          : "text-red-600"

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Conversaciones */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Conversaciones Generadas
          </CardTitle>
          <MessageSquare className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {totalConversions > 0
              ? totalConversions.toLocaleString("es-CO")
              : "Sin datos aún"}
          </div>
          {totalConversions > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              clientes contactados por WhatsApp
            </p>
          )}
        </CardContent>
      </Card>

      {/* Dinero Ahorrado */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger className="cursor-help underline decoration-dashed underline-offset-4">
                  Dinero Ahorrado
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-sm">
                  Estimación basada en el presupuesto semanal que habrían
                  consumido las campañas pausadas
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </CardTitle>
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-emerald-600">
            ~{formatUSD(moneySaved)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {totalKilled} campaña{totalKilled !== 1 ? "s" : ""} inefectiva
            {totalKilled !== 1 ? "s" : ""} pausada{totalKilled !== 1 ? "s" : ""}
          </p>
        </CardContent>
      </Card>

      {/* ROAS */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger className="cursor-help underline decoration-dashed underline-offset-4">
                  ROAS Promedio
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-sm">
                  Retorno sobre inversión publicitaria: por cada peso que inviertes en anuncios, cuánto ganas de vuelta
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {avgRoas > 0 ? (
            <>
              <div className={cn("text-2xl font-bold", roasFormatted.color)}>
                {roasFormatted.text}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Por cada $1 invertido, ganas ${avgRoas.toLocaleString("es-CO", { maximumFractionDigits: 1 })}
              </p>
            </>
          ) : (
            <div className="text-2xl font-bold text-muted-foreground">
              Sin datos suficientes
            </div>
          )}
        </CardContent>
      </Card>

      {/* CPA */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger className="cursor-help underline decoration-dashed underline-offset-4">
                  Costo por Conversación
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-sm">
                  Costo por conversación: cada conversación en WhatsApp te cuesta este valor
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </CardTitle>
          <Target className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {costPerConv > 0 ? (
            <>
              <div className={cn("text-2xl font-bold", cpaColor)}>
                {formatUSD(costPerConv)}
              </div>
              {targetCpa > 0 && (
                <p className="text-xs text-muted-foreground mt-1">
                  Objetivo: {formatUSD(targetCpa)}
                </p>
              )}
            </>
          ) : (
            <div className="text-2xl font-bold text-muted-foreground">
              Sin datos suficientes
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
