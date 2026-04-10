import { Link } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatROAS, formatUSD } from "@/lib/formatters"
import { MetricTooltip } from "./MetricTooltip"
import type { TopPerformer } from "@/types"
import { cn } from "@/lib/utils"

interface TopPerformersPodiumProps {
  performers: TopPerformer[]
  getName: (id: string) => string
}

const MEDALS = ["🥇", "🥈", "🥉"]
const BORDER_COLORS = [
  "border-yellow-400",
  "border-gray-300",
  "border-amber-600",
]
const BG_COLORS = [
  "bg-yellow-50/50",
  "bg-gray-50/50",
  "bg-amber-50/50",
]

export default function TopPerformersPodium({
  performers,
  getName,
}: TopPerformersPodiumProps) {
  if (!performers?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Mejores campañas</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center gap-2">
            <p className="text-muted-foreground">
              Publica campañas para ver tu podio de mejores anuncios
            </p>
            <Link to="/campaigns" className="text-sm text-primary hover:underline">
              Ir a campañas &rarr;
            </Link>
          </div>
        </CardContent>
      </Card>
    )
  }

  const top3 = performers.slice(0, 3)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Mejores campañas</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col md:flex-row gap-4">
          {top3.map((p, i) => {
            const roas = formatROAS(p.roas ?? 0)
            return (
              <Card
                key={p.campaign_id}
                className={cn(
                  "flex-1 border-2",
                  BORDER_COLORS[i],
                  BG_COLORS[i],
                  i === 0 && "md:scale-105 md:shadow-md"
                )}
              >
                <CardContent className="pt-4 space-y-2 text-center">
                  <span className="text-2xl">{MEDALS[i]}</span>
                  <p className="font-medium text-sm leading-tight">
                    {getName(p.campaign_id)}
                  </p>
                  <div className="space-y-1 text-xs">
                    <MetricTooltip
                      label="ROAS"
                      value={roas.text}
                      tooltip="Retorno sobre inversión publicitaria: por cada peso que inviertes en anuncios, cuánto ganas de vuelta"
                    />
                    <br />
                    <MetricTooltip
                      label="CPC"
                      value={p.cpc_cents != null ? formatUSD(p.cpc_cents) : "—"}
                      tooltip="Costo por clic: cada clic en tu anuncio cuesta este valor"
                    />
                    <br />
                    <span className="text-muted-foreground">
                      Conversiones:{" "}
                      <span className="font-medium text-foreground">
                        {p.conversions ?? "—"}
                      </span>
                    </span>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
