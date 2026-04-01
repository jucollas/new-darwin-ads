import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  Megaphone,
  DollarSign,
  Plus,
  Eye,
  MousePointerClick,
  Clock,
} from "lucide-react"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/StatusBadge"
import type {
  MetricsSummary,
  Campaign,
  PaginatedResponse,
  OptimizationRun,
} from "@/types"

function DashboardMetricCard({
  title,
  value,
  icon: Icon,
  loading,
}: {
  title: string
  value: string | number
  icon: React.ElementType
  loading: boolean
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <div className="text-2xl font-bold">{value}</div>
        )}
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()

  const summaryQuery = useQuery<MetricsSummary>({
    queryKey: ["metrics-summary"],
    queryFn: () => api.get(ENDPOINTS.metrics.summary).then((r) => r.data),
    retry: false,
  })

  const campaignsQuery = useQuery<Campaign[]>({
    queryKey: ["campaigns-recent"],
    queryFn: () =>
      api
        .get(ENDPOINTS.campaigns.list, { params: { page: 1, page_size: 5 } })
        .then((r) => {
          const body = r.data
          if (Array.isArray(body)) return body
          return (body as PaginatedResponse<Campaign>).items ?? []
        }),
    retry: false,
  })

  const optimizeQuery = useQuery<OptimizationRun[]>({
    queryKey: ["optimize-recent"],
    queryFn: () =>
      api
        .get(ENDPOINTS.optimize.history, { params: { page: 1, page_size: 5 } })
        .then((r) => {
          const body = r.data
          if (Array.isArray(body)) return body
          return (body as PaginatedResponse<OptimizationRun>).items ?? []
        }),
    retry: false,
  })

  const summary = summaryQuery.data
  const sLoading = summaryQuery.isLoading

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Resumen general de tu sistema
        </p>
      </div>

      {/* Metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <DashboardMetricCard
          title="Campañas activas"
          value={summary?.active_campaigns ?? 0}
          icon={Megaphone}
          loading={sLoading}
        />
        <DashboardMetricCard
          title="Impresiones totales"
          value={(summary?.total_impressions ?? 0).toLocaleString()}
          icon={Eye}
          loading={sLoading}
        />
        <DashboardMetricCard
          title="Clicks totales"
          value={(summary?.total_clicks ?? 0).toLocaleString()}
          icon={MousePointerClick}
          loading={sLoading}
        />
        <DashboardMetricCard
          title="Gasto total"
          value={`$${((summary?.total_spend_cents ?? 0) / 100).toFixed(2)}`}
          icon={DollarSign}
          loading={sLoading}
        />
      </div>

      {/* Recent campaigns */}
      <Card>
        <CardHeader>
          <CardTitle>Campañas recientes</CardTitle>
          <CardDescription>
            Últimas 5 campañas actualizadas
          </CardDescription>
        </CardHeader>
        <CardContent>
          {campaignsQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !campaignsQuery.data?.length ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No hay campañas aún
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">Campaña</th>
                    <th className="pb-2 font-medium">Estado</th>
                    <th className="pb-2 font-medium text-right">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {campaignsQuery.data.map((campaign) => (
                    <tr
                      key={campaign.id}
                      className="border-b last:border-0 cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => navigate(`/campaigns/${campaign.id}`)}
                    >
                      <td className="py-3 font-medium max-w-xs truncate">
                        {campaign.user_prompt.length > 60
                          ? campaign.user_prompt.slice(0, 60) + "..."
                          : campaign.user_prompt}
                      </td>
                      <td className="py-3">
                        <StatusBadge status={campaign.status} />
                      </td>
                      <td className="py-3 text-right text-muted-foreground">
                        {new Date(campaign.updated_at).toLocaleDateString(
                          "es-ES",
                          {
                            day: "numeric",
                            month: "short",
                          },
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Optimization runs */}
      <Card>
        <CardHeader>
          <CardTitle>Actividad del algoritmo genético</CardTitle>
          <CardDescription>Últimas 5 ejecuciones de optimización</CardDescription>
        </CardHeader>
        <CardContent>
          {optimizeQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !optimizeQuery.data?.length ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Sin actividad reciente
            </p>
          ) : (
            <div className="space-y-3">
              {optimizeQuery.data.map((run) => (
                <div
                  key={run.id}
                  className="flex items-start gap-3 rounded-lg border p-3"
                >
                  <div className="mt-0.5 rounded-full bg-muted p-2">
                    <Clock className="h-4 w-4" />
                  </div>
                  <div className="flex-1 space-y-1">
                    <p className="text-sm">
                      Generación #{run.generation_number} — {run.campaigns_evaluated} campañas evaluadas
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>
                        Duplicadas: {run.campaigns_duplicated.length}
                      </span>
                      <span>·</span>
                      <span>
                        Eliminadas: {run.campaigns_killed.length}
                      </span>
                      <span>·</span>
                      <span>
                        {new Date(run.ran_at).toLocaleDateString("es-ES", {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Floating action button */}
      <Button
        className="fixed bottom-6 right-6 h-14 gap-2 rounded-full px-6 shadow-lg"
        onClick={() => navigate("/campaigns/new")}
      >
        <Plus className="h-5 w-5" />
        Nueva Campaña
      </Button>
    </div>
  )
}
