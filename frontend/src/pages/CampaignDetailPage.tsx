import { useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { toast } from "sonner"
import {
  DollarSign,
  Eye,
  MousePointerClick,
  Target,
  Pencil,
  Trash2,
  ChevronRight,
  Image as ImageIcon,
  Loader2,
  Pause,
  Play,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { MetricCard } from "@/components/MetricCard"
import { StatusBadge } from "@/components/StatusBadge"
import type { Campaign, Proposal, CampaignMetric } from "@/types"

export default function CampaignDetailPage() {
  const { campaignId } = useParams<{ campaignId: string }>()
  const navigate = useNavigate()
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  const { data: campaign, isLoading: campaignLoading } = useQuery<Campaign>({
    queryKey: ["campaign", campaignId],
    queryFn: () =>
      api.get(ENDPOINTS.campaigns.detail(campaignId!)).then((r) => r.data),
  })

  const { data: proposals = [] } = useQuery<Proposal[]>({
    queryKey: ["campaign-proposals", campaignId],
    queryFn: () =>
      api.get(ENDPOINTS.campaigns.proposals(campaignId!)).then((r) => {
        const body = r.data
        return Array.isArray(body) ? body : body.items ?? []
      }),
  })

  const { data: metrics = [] } = useQuery<CampaignMetric[]>({
    queryKey: ["campaign-metrics", campaignId],
    queryFn: () =>
      api.get(ENDPOINTS.metrics.byCampaign(campaignId!)).then((r) => {
        const body = r.data
        return Array.isArray(body) ? body : body.items ?? []
      }),
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(ENDPOINTS.campaigns.delete(campaignId!)),
    onSuccess: () => {
      toast.success("Campaña eliminada correctamente")
      queryClient.invalidateQueries({ queryKey: ["campaigns"] })
      navigate("/campaigns")
    },
    onError: () => {
      toast.error("Error al eliminar la campaña")
    },
  })

  const pauseMutation = useMutation({
    mutationFn: () => api.post(ENDPOINTS.campaigns.pause(campaignId!)),
    onSuccess: () => {
      toast.success("Campaña pausada")
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] })
    },
    onError: () => toast.error("Error al pausar la campaña"),
  })

  const resumeMutation = useMutation({
    mutationFn: () => api.post(ENDPOINTS.campaigns.resume(campaignId!)),
    onSuccess: () => {
      toast.success("Campaña reactivada")
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] })
    },
    onError: () => toast.error("Error al reactivar la campaña"),
  })

  // Aggregate metrics
  const totalSpendCents = metrics.reduce((sum, m) => sum + m.spend_cents, 0)
  const totalImpressions = metrics.reduce((sum, m) => sum + m.impressions, 0)
  const totalClicks = metrics.reduce((sum, m) => sum + m.clicks, 0)
  const totalConversions = metrics.reduce((sum, m) => sum + m.conversions, 0)

  const selectedProposal = proposals.find((p) => p.is_selected)
  const campaignTitle = campaign
    ? campaign.user_prompt.length > 60
      ? campaign.user_prompt.slice(0, 60) + "..."
      : campaign.user_prompt
    : ""

  if (campaignLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground">Campaña no encontrada</p>
        <Button variant="link" asChild>
          <Link to="/campaigns">Volver a campañas</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link to="/campaigns" className="hover:text-foreground">
          Campañas
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="text-foreground">{campaignTitle}</span>
      </nav>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{campaignTitle}</h1>
            <StatusBadge status={campaign.status} />
          </div>
          <p className="text-muted-foreground">{campaign.user_prompt}</p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to={`/campaigns/${campaignId}/edit`}>
              <Pencil className="mr-1 h-4 w-4" />
              Editar
            </Link>
          </Button>
          {campaign.status === "published" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => pauseMutation.mutate()}
              disabled={pauseMutation.isPending}
            >
              {pauseMutation.isPending ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <Pause className="mr-1 h-4 w-4" />
              )}
              Pausar
            </Button>
          )}
          {campaign.status === "paused" && (
            <Button
              size="sm"
              onClick={() => resumeMutation.mutate()}
              disabled={resumeMutation.isPending}
            >
              {resumeMutation.isPending ? (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-1 h-4 w-4" />
              )}
              Reactivar
            </Button>
          )}
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setDeleteDialogOpen(true)}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            Eliminar
          </Button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Gasto total"
          value={`$${(totalSpendCents / 100).toFixed(2)}`}
          icon={DollarSign}
        />
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
          title="Conversiones"
          value={totalConversions.toLocaleString()}
          icon={Target}
        />
      </div>

      {/* Proposals section */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">
          Propuestas{" "}
          <span className="text-muted-foreground font-normal">
            ({proposals.length})
          </span>
        </h2>

        {proposals.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <ImageIcon className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                Esta campaña no tiene propuestas aún
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {proposals.map((proposal) => (
              <Card
                key={proposal.id}
                className={`${proposal.is_selected ? "border-primary" : ""}`}
              >
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    {proposal.is_selected && (
                      <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded-full">
                        Seleccionada
                      </span>
                    )}
                    {proposal.copy_text.slice(0, 50)}...
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {proposal.image_url && (
                    <img
                      src={proposal.image_url}
                      alt=""
                      className="w-full h-32 object-cover rounded"
                    />
                  )}
                  <div>
                    <span className="font-medium">Script: </span>
                    <span className="text-muted-foreground line-clamp-2">{proposal.script}</span>
                  </div>
                  <div>
                    <span className="font-medium">CTA: </span>
                    {proposal.cta_type}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(proposal.created_at).toLocaleDateString("es-ES", {
                      day: "numeric",
                      month: "short",
                    })}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar campaña</DialogTitle>
            <DialogDescription>
              Esta acción no se puede deshacer. Se eliminarán todas las
              propuestas asociadas a esta campaña.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                deleteMutation.mutate()
                setDeleteDialogOpen(false)
              }}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              )}
              Eliminar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
