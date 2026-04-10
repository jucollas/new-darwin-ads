import { useNavigate, useParams, Link } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { toast } from "sonner"
import { useUIStore } from "@/store/ui.store"
import type { Publication, Campaign, CampaignMetric } from "@/types"
import {
  Pause,
  Trash,
  Play,
  Eye,
  MousePointerClick,
  DollarSign,
  BarChart3,
  Target,
  ChevronRight,
  Loader2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/StatusBadge"
import { MetricCard } from "@/components/MetricCard"
import { formatGeoLocations } from "@/lib/formatters"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts"

export default function PublicationDetailPage() {
  const { publicationId } = useParams<{ publicationId: string }>()
  const navigate = useNavigate()
  const openConfirmDialog = useUIStore((s) => s.openConfirmDialog)

  // Fetch publication
  const {
    data: publication,
    isLoading,
    isError,
  } = useQuery<Publication>({
    queryKey: ["publication", publicationId],
    queryFn: () =>
      api
        .get(ENDPOINTS.publish.publicationStatus(publicationId!))
        .then((r) => r.data),
    enabled: !!publicationId,
  })

  // Fetch campaign detail (includes proposals)
  const { data: campaign } = useQuery<Campaign>({
    queryKey: ["campaign", publication?.campaign_id],
    queryFn: () =>
      api
        .get(ENDPOINTS.campaigns.detail(publication!.campaign_id))
        .then((r) => r.data),
    enabled: !!publication?.campaign_id,
  })

  // Fetch metrics for campaign
  const { data: metrics = [] } = useQuery<CampaignMetric[]>({
    queryKey: ["publication-metrics", publication?.campaign_id],
    queryFn: () =>
      api
        .get(ENDPOINTS.metrics.byCampaign(publication!.campaign_id))
        .then((r) => {
          const body = r.data
          return Array.isArray(body) ? body : body.items ?? []
        }),
    enabled: !!publication?.campaign_id && publication?.status === "active",
  })

  const pauseMutation = useMutation({
    mutationFn: () =>
      api.post(ENDPOINTS.publish.pausePublication(publicationId!)),
    onSuccess: () => {
      toast.success("Publicación pausada")
      queryClient.invalidateQueries({
        queryKey: ["publication", publicationId],
      })
    },
    onError: () => toast.error("Error al pausar"),
  })

  const resumeMutation = useMutation({
    mutationFn: () =>
      api.post(ENDPOINTS.publish.resumePublication(publicationId!)),
    onSuccess: () => {
      toast.success("Publicación reactivada")
      queryClient.invalidateQueries({
        queryKey: ["publication", publicationId],
      })
    },
    onError: () => toast.error("Error al reactivar"),
  })

  const deleteMutation = useMutation({
    mutationFn: () =>
      api.delete(ENDPOINTS.publish.deletePublication(publicationId!)),
    onSuccess: () => {
      toast.success("Publicación eliminada")
      navigate(-1)
    },
    onError: () => toast.error("Error al eliminar"),
  })

  const handleDelete = () => {
    openConfirmDialog({
      title: "Eliminar publicación",
      message:
        "¿Estás seguro de que deseas eliminar esta publicación? Esta acción no se puede deshacer.",
      onConfirm: () => deleteMutation.mutate(),
    })
  }

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    )
  }

  if (isError || !publication) {
    return (
      <div className="flex flex-col items-center justify-center p-12 gap-4">
        <p className="text-muted-foreground">No se encontró la publicación.</p>
        <Button variant="outline" onClick={() => navigate(-1)}>
          Volver
        </Button>
      </div>
    )
  }

  // Find the selected proposal from campaign data
  const selectedProposal = campaign?.proposals?.find(
    (p) => p.id === publication.proposal_id,
  )

  // Aggregate metrics
  const totalSpendCents = metrics.reduce((sum, m) => sum + m.spend_cents, 0)
  const totalImpressions = metrics.reduce((sum, m) => sum + m.impressions, 0)
  const totalClicks = metrics.reduce((sum, m) => sum + m.clicks, 0)
  const totalConversions = metrics.reduce((sum, m) => sum + m.conversions, 0)
  const avgCtr =
    totalImpressions > 0
      ? ((totalClicks / totalImpressions) * 100).toFixed(2)
      : "0.00"
  const avgCpc =
    totalClicks > 0 ? (totalSpendCents / 100 / totalClicks).toFixed(2) : "0.00"

  // Chart data
  const chartData = metrics.map((m) => ({
    date: m.date,
    impressions: m.impressions,
    clicks: m.clicks,
    conversions: m.conversions,
  }))

  return (
    <div className="space-y-8 p-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link
          to="/campaigns"
          className="hover:text-foreground transition-colors"
        >
          Campañas
        </Link>
        <ChevronRight className="h-4 w-4" />
        {publication.campaign_id && (
          <>
            <Link
              to={`/campaigns/${publication.campaign_id}`}
              className="hover:text-foreground transition-colors"
            >
              Campaña
            </Link>
            <ChevronRight className="h-4 w-4" />
          </>
        )}
        <span className="text-foreground font-medium">Publicación</span>
      </nav>

      {/* Header */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Publicación</h1>
          <StatusBadge status={publication.status} />
        </div>

        {/* Budget & Location */}
        <p className="text-muted-foreground">
          Presupuesto diario: ${(publication.budget_daily_cents / 100).toFixed(2)}
        </p>
        <p className="text-muted-foreground">
          Ubicación: {formatGeoLocations(publication.resolved_geo_locations)}
        </p>

        {/* Selected proposal info */}
        {selectedProposal && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Propuesta seleccionada
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {selectedProposal.image_url && (
                <img
                  src={selectedProposal.image_url}
                  alt=""
                  className="w-full max-h-60 object-contain rounded"
                />
              )}
              <p>{selectedProposal.copy_text}</p>
              {selectedProposal.script && (
                <p className="text-muted-foreground whitespace-pre-line">
                  {selectedProposal.script}
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          {publication.status === "active" && (
            <Button
              variant="outline"
              onClick={() => pauseMutation.mutate()}
              disabled={pauseMutation.isPending}
            >
              {pauseMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Pause className="h-4 w-4 mr-2" />
              )}
              Pausar
            </Button>
          )}

          {publication.status === "paused" && (
            <>
              <Button
                onClick={() => resumeMutation.mutate()}
                disabled={resumeMutation.isPending}
              >
                {resumeMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                Reactivar
              </Button>
              <Button variant="destructive" onClick={handleDelete}>
                <Trash className="h-4 w-4 mr-2" />
                Eliminar
              </Button>
            </>
          )}

          {publication.status === "failed" && (
            <Button variant="destructive" onClick={handleDelete}>
              <Trash className="h-4 w-4 mr-2" />
              Eliminar
            </Button>
          )}
        </div>
      </div>

      {/* Metrics Section (only if active) */}
      {publication.status === "active" && metrics.length > 0 && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold">Métricas</h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              title="Impresiones"
              value={totalImpressions.toLocaleString()}
              icon={Eye}
            />
            <MetricCard
              title="Clicks"
              value={totalClicks.toLocaleString()}
              icon={MousePointerClick}
            />
            <MetricCard
              title="CTR"
              value={`${avgCtr}%`}
              icon={BarChart3}
            />
            <MetricCard
              title="CPC"
              value={`$${avgCpc}`}
              icon={Target}
            />
            <MetricCard
              title="Gasto"
              value={`$${(totalSpendCents / 100).toFixed(2)}`}
              icon={DollarSign}
            />
            <MetricCard
              title="Conversiones"
              value={totalConversions.toLocaleString()}
              icon={Target}
            />
          </div>

          {/* Line Chart */}
          {chartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Rendimiento últimos días
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(0 0% 20%)"
                    />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      stroke="hsl(0 0% 40%)"
                    />
                    <YAxis tick={{ fontSize: 12 }} stroke="hsl(0 0% 40%)" />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: "hsl(0 0% 10%)",
                        border: "1px solid hsl(0 0% 20%)",
                        borderRadius: "8px",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="impressions"
                      name="Impresiones"
                      stroke="hsl(262, 83%, 58%)"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="conversions"
                      name="Conversiones"
                      stroke="#22c55e"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Error message */}
      {publication.error_message && (
        <Card className="border-destructive">
          <CardContent className="p-4">
            <p className="text-sm text-destructive">
              <span className="font-medium">Error: </span>
              {publication.error_message}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
