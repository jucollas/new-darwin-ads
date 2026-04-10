import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts"
import { BarChart3 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatShortDate } from "@/lib/formatters"

interface ChartDataPoint {
  date: string
  avgRoas: number
  avgCostPerConv: number
}

interface PerformanceChartProps {
  data: ChartDataPoint[]
}

function CustomTooltip({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ value: number; dataKey: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-background p-3 shadow-sm">
      <p className="text-sm font-medium mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="text-sm text-muted-foreground">
          {p.dataKey === "avgRoas"
            ? `ROAS: ${p.value.toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}×`
            : `Costo/conv: $${Math.round(p.value).toLocaleString("es-CO")}`}
        </p>
      ))}
    </div>
  )
}

export default function PerformanceChart({ data }: PerformanceChartProps) {
  if (data.length < 2) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tendencia de rendimiento</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
            <BarChart3 className="h-12 w-12 text-muted-foreground/50" />
            <p className="text-muted-foreground">
              El sistema necesita al menos 2 optimizaciones para mostrar tendencias.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const chartData = data.map((d) => ({
    ...d,
    label: formatShortDate(d.date),
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Tendencia de rendimiento</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 12 }}
              label={{ value: "ROAS", angle: -90, position: "insideLeft", fontSize: 12 }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 12 }}
              label={{ value: "USD/conv", angle: 90, position: "insideRight", fontSize: 12 }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="avgRoas"
              fill="hsl(142, 76%, 36%)"
              fillOpacity={0.15}
              stroke="hsl(142, 76%, 36%)"
              strokeWidth={2}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="avgCostPerConv"
              stroke="hsl(217, 91%, 60%)"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
        <div className="flex items-center justify-center gap-6 mt-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-emerald-500/30 border border-emerald-600" />
            ROAS promedio
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-blue-500 border border-blue-600" />
            Costo por conversación
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
