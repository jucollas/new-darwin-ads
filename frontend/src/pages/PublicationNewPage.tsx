import { useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { toast } from "sonner"
import {
  ChevronRight,
  Loader2,
  Send,
  ArrowLeft,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Campaign, Proposal, AdAccount } from "@/types"

export default function PublicationNewPage() {
  const { campaignId } = useParams<{ campaignId: string }>()
  const navigate = useNavigate()

  const [selectedAccountId, setSelectedAccountId] = useState("")
  const [budgetDollars, setBudgetDollars] = useState("")

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

  const { data: adAccounts = [], isLoading: accountsLoading } = useQuery<AdAccount[]>({
    queryKey: ["ad-accounts"],
    queryFn: () =>
      api.get(ENDPOINTS.publish.adAccounts).then((r) => {
        const body = r.data
        return Array.isArray(body) ? body : body.items ?? []
      }),
  })

  const selectedProposal = proposals.find((p) => p.is_selected) ?? proposals[0]

  const publishMutation = useMutation({
    mutationFn: () =>
      api.post(ENDPOINTS.campaigns.publish(campaignId!), {
        ad_account_id: selectedAccountId,
        budget_daily_cents: Math.round(Number(budgetDollars) * 100),
      }),
    onSuccess: () => {
      toast.success("Campaña publicada exitosamente")
      queryClient.invalidateQueries({ queryKey: ["campaigns"] })
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] })
      navigate(`/campaigns/${campaignId}`)
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Error al publicar")
    },
  })

  const campaignTitle = campaign
    ? campaign.user_prompt.length > 40
      ? campaign.user_prompt.slice(0, 40) + "..."
      : campaign.user_prompt
    : "..."

  if (campaignLoading || accountsLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link to="/campaigns" className="hover:text-foreground">
          Campañas
        </Link>
        <ChevronRight className="h-4 w-4" />
        <Link
          to={`/campaigns/${campaignId}`}
          className="hover:text-foreground"
        >
          {campaignTitle}
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="text-foreground">Publicar</span>
      </nav>

      <h1 className="text-2xl font-bold">Publicar campaña</h1>

      {/* Selected proposal summary */}
      {selectedProposal && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Propuesta seleccionada</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {selectedProposal.image_url && (
              <img
                src={selectedProposal.image_url}
                alt=""
                className="w-full max-h-48 object-contain rounded"
              />
            )}
            <div>
              <span className="font-medium">Copy: </span>
              {selectedProposal.copy_text}
            </div>
            <div>
              <span className="font-medium">Script: </span>
              {selectedProposal.script}
            </div>
            <div>
              <span className="font-medium">CTA: </span>
              {selectedProposal.cta_type}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Publication settings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Configuración de publicación</CardTitle>
          <CardDescription>
            Selecciona la cuenta de anuncios y el presupuesto diario
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Cuenta de anuncios</label>
            {adAccounts.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No tienes cuentas de anuncios conectadas.{" "}
                <Link to="/profile" className="text-primary hover:underline">
                  Conecta Meta en tu perfil
                </Link>
              </p>
            ) : (
              <Select
                value={selectedAccountId}
                onValueChange={setSelectedAccountId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selecciona una cuenta" />
                </SelectTrigger>
                <SelectContent>
                  {adAccounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.meta_ad_account_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Presupuesto diario ($)
            </label>
            <Input
              type="number"
              min={1}
              step="0.01"
              placeholder="10.00"
              value={budgetDollars}
              onChange={(e) => setBudgetDollars(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={() => navigate(`/campaigns/${campaignId}`)}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver
        </Button>
        <Button
          onClick={() => publishMutation.mutate()}
          disabled={
            publishMutation.isPending ||
            !selectedAccountId ||
            !budgetDollars ||
            Number(budgetDollars) <= 0
          }
        >
          {publishMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Send className="mr-2 h-4 w-4" />
          )}
          Publicar ahora
        </Button>
      </div>
    </div>
  )
}
