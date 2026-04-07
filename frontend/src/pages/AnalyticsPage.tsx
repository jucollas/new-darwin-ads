import { useState, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import {
  Eye,
  MousePointerClick,
  DollarSign,
  MessageCircle,
  Percent,
  TrendingUp,
  RefreshCw,
  Loader2,
  BarChart3,
  AlertCircle,
  Plus,
} from "lucide-react"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { MetricCard } from "@/components/MetricCard"
import {
  useMetricsSummary,
  useTopPerformers,
  useUnderperformers,
  useCampaignMetrics,
  useCollectMetrics,
} from "@/hooks/useAnalytics"
import { formatCurrency, formatPercent, formatROAS, cn } from "@/lib/utils"

function getDefaultDateRange() {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 30)
  return {
    from: from.toISOString().split("T")[0],
    to: to.toISOString().split("T")[0],
  }
}

export default function AnalyticsPage() {
  const navigate = useNavigate()
  const defaults = getDefaultDateRange()
  const [fromDate, setFromDate] = useState(defaults.from)
  const [toDate, setToDate] = useState(defaults.to)

  const summaryQuery = useMetricsSummary()
  const topQuery = useTopPerformers()
  const underQuery = useUnderperformers()
  const collectMutation = useCollectMetrics()

  // Fetch chart data from top performer's campaign
  const topCampaignId = topQuery.data?.[0]?.campaign_id ?? ""
  const chartQuery = useCampaignMetrics(topCampaignId, fromDate, toDate)

  const summary = summaryQuery.data
  const isLoading = summaryQuery.isLoading
  const isError = summaryQuery.isError

  // Prepare chart data sorted by date
  const chartData = useMemo(() => {
    if (!chartQuery.data?.items?.length) return []
    return [...chartQuery.data.items]
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((m) => ({
        date: m.date,
        impressions: m.impressions,
        clicks: m.clicks,
        spend: m.spend_cents / 100,
      }))
  }, [chartQuery.data])

  // Stale data check
  const latestCollectedAt = chartQuery.data?.items?.[0]?.collected_at
  const isStale = useMemo(() => {
    if (!latestCollectedAt) return false
    const hoursAgo =
      (Date.now() - new Date(latestCollectedAt).getTime()) / (1000 * 60 * 60)
    return hoursAgo > 12
  }, [latestCollectedAt])

  if (isError) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold">Analytics</h1>
        </div>
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex items-center gap-3 py-6">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <div className="flex-1">
              <p className="font-medium text-destructive">
                Error al cargar los datos de analytics
              </p>
              <p className="text-sm text-muted-foreground">
                Intenta de nuevo más tarde.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => summaryQuery.refetch()}
            >
              Reintentar
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold">Analytics</h1>
          {summary && (
            <Badge variant="secondary">
              {summary.active_campaigns} campaña{summary.active_campaigns !== 1 ? "s" : ""} activa{summary.active_campaigns !== 1 ? "s" : ""}
            </Badge>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex items-end gap-2">
            <div>
              <Label htmlFor="from-date" className="text-xs">Desde</Label>
              <Input
                id="from-date"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="w-36"
              />
            </div>
            <div>
              <Label htmlFor="to-date" className="text-xs">Hasta</Label>
              <Input
                id="to-date"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="w-36"
              />
            </div>
          </div>
          <Button
            onClick={() => collectMutation.mutate(undefined)}
            disabled={collectMutation.isPending}
          >
            {collectMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Actualizar datos
          </Button>
        </div>
      </div>

      {/* Stale data notice */}
      {isStale && (
        <Card className="border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950">
          <CardContent className="flex items-center gap-3 py-3">
            <AlertCircle className="h-4 w-4 text-yellow-600" />
            <p className="text-sm text-yellow-700 dark:text-yellow-400">
              Los datos fueron actualizados hace más de 12 horas. Haz clic en "Actualizar datos" para recolectar las métricas más recientes.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Summary cards */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))
        ) : (
          <>
            <MetricCard
              title="Impresiones totales"
              value={(summary?.total_impressions ?? 0).toLocaleString()}
              icon={Eye}
            />
            <MetricCard
              title="Clicks totales"
              value={(summary?.total_clicks ?? 0).toLocaleString()}
              icon={MousePointerClick}
            />
            <MetricCard
              title="Gasto total"
              value={formatCurrency(summary?.total_spend_cents ?? 0)}
              icon={DollarSign}
            />
            <MetricCard
              title="Conversiones"
              value={(summary?.total_conversions ?? 0).toLocaleString()}
              icon={MessageCircle}
            />
          </>
        )}
      </div>

      {/* Secondary stats */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))
        ) : (
          <>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">CTR Promedio</CardTitle>
                <Percent className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div
                  className={cn(
                    "text-2xl font-bold",
                    (summary?.avg_ctr ?? 0) > 2
                      ? "text-green-600"
                      : (summary?.avg_ctr ?? 0) >= 1
                        ? "text-yellow-600"
                        : "text-red-600"
                  )}
                >
                  {formatPercent(summary?.avg_ctr ?? 0)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">CPC Promedio</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {formatCurrency(summary?.avg_cpc_cents ?? 0)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">ROAS Promedio</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div
                  className={cn(
                    "text-2xl font-bold",
                    (summary?.avg_roas ?? 0) >= 1 ? "text-green-600" : "text-red-600"
                  )}
                >
                  {formatROAS(summary?.avg_roas ?? 0)}
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Performance chart */}
      <Card>
        <CardHeader>
          <CardTitle>Rendimiento en el tiempo</CardTitle>
          <CardDescription>
            {topCampaignId
              ? `Campaña: ${topCampaignId.slice(0, 8)}...`
              : "Métricas diarias de la campaña principal"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {chartQuery.isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : chartData.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <BarChart3 className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                No hay métricas disponibles aún. Publica una campaña y espera la recolección de datos.
              </p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => navigate("/campaigns/new")}
              >
                <Plus className="mr-2 h-4 w-4" />
                Crear campaña
              </Button>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorImpressions" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorClicks" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorSpend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v) =>
                    new Date(v + "T00:00:00").toLocaleDateString("es-ES", {
                      day: "numeric",
                      month: "short",
                    })
                  }
                  className="text-xs"
                />
                <YAxis yAxisId="left" className="text-xs" />
                <YAxis yAxisId="right" orientation="right" className="text-xs" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                  formatter={(value: number, name: string) => {
                    if (name === "spend") return [`$${value.toFixed(0)}`, "Gasto"]
                    if (name === "impressions") return [value.toLocaleString(), "Impresiones"]
                    return [value.toLocaleString(), "Clicks"]
                  }}
                  labelFormatter={(label) =>
                    new Date(label + "T00:00:00").toLocaleDateString("es-ES", {
                      day: "numeric",
                      month: "long",
                    })
                  }
                />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="impressions"
                  stroke="#3b82f6"
                  fill="url(#colorImpressions)"
                  strokeWidth={2}
                />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="clicks"
                  stroke="#22c55e"
                  fill="url(#colorClicks)"
                  strokeWidth={2}
                />
                <Area
                  yAxisId="right"
                  type="monotone"
                  dataKey="spend"
                  stroke="#f97316"
                  fill="url(#colorSpend)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Top performers & Underperformers */}
      <div className="grid gap-6 grid-cols-1 md:grid-cols-2">
        {/* Top Performers */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-green-600" />
              Top Performers
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topQuery.isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : !topQuery.data?.length ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                Sin datos de rendimiento aún
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 font-medium">Campaña</th>
                      <th className="pb-2 font-medium text-right">Impresiones</th>
                      <th className="pb-2 font-medium text-right">Clicks</th>
                      <th className="pb-2 font-medium text-right">CTR</th>
                      <th className="pb-2 font-medium text-right">ROAS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topQuery.data.map((item) => (
                      <tr
                        key={item.campaign_id}
                        className="border-b last:border-0 cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => navigate(`/campaigns/${item.campaign_id}`)}
                      >
                        <td className="py-3 font-medium font-mono text-xs">
                          {item.campaign_id.slice(0, 8)}...
                        </td>
                        <td className="py-3 text-right">
                          {item.impressions.toLocaleString()}
                        </td>
                        <td className="py-3 text-right">
                          {item.clicks.toLocaleString()}
                        </td>
                        <td className="py-3 text-right text-green-600">
                          {formatPercent(item.ctr)}
                        </td>
                        <td className="py-3 text-right text-green-600">
                          {formatROAS(item.roas)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Underperformers */}
        <Card className="border-red-200/50 dark:border-red-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-500" />
              Bajo rendimiento
            </CardTitle>
          </CardHeader>
          <CardContent>
            {underQuery.isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : !underQuery.data?.length ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                Sin datos de rendimiento aún
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="pb-2 font-medium">Campaña</th>
                      <th className="pb-2 font-medium text-right">Impresiones</th>
                      <th className="pb-2 font-medium text-right">Clicks</th>
                      <th className="pb-2 font-medium text-right">CTR</th>
                      <th className="pb-2 font-medium text-right">ROAS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {underQuery.data.map((item) => (
                      <tr
                        key={item.campaign_id}
                        className="border-b last:border-0 cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => navigate(`/campaigns/${item.campaign_id}`)}
                      >
                        <td className="py-3 font-medium font-mono text-xs">
                          {item.campaign_id.slice(0, 8)}...
                        </td>
                        <td className="py-3 text-right">
                          {item.impressions.toLocaleString()}
                        </td>
                        <td className="py-3 text-right">
                          {item.clicks.toLocaleString()}
                        </td>
                        <td className="py-3 text-right text-red-500">
                          {formatPercent(item.ctr)}
                        </td>
                        <td className="py-3 text-right text-red-500">
                          {formatROAS(item.roas)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
