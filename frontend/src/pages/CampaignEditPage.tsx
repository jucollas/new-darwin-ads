import { useParams, useNavigate, Link } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { toast } from "sonner"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { ChevronRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { Campaign } from "@/types"

const campaignSchema = z.object({
  user_prompt: z.string().min(3, "El prompt debe tener al menos 3 caracteres"),
})

type CampaignFormValues = z.infer<typeof campaignSchema>

export default function CampaignEditPage() {
  const { campaignId } = useParams<{ campaignId: string }>()
  const navigate = useNavigate()

  const { data: campaign, isLoading } = useQuery<Campaign>({
    queryKey: ["campaign", campaignId],
    queryFn: () =>
      api.get(ENDPOINTS.campaigns.detail(campaignId!)).then((r) => r.data),
  })

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignSchema),
    values: campaign
      ? {
          user_prompt: campaign.user_prompt,
        }
      : undefined,
  })

  const saveMutation = useMutation({
    mutationFn: (data: CampaignFormValues) =>
      api.put(ENDPOINTS.campaigns.update(campaignId!), data),
    onSuccess: () => {
      toast.success("Campaña actualizada correctamente")
      queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] })
      queryClient.invalidateQueries({ queryKey: ["campaigns"] })
      navigate(`/campaigns/${campaignId}`)
    },
    onError: () => {
      toast.error("Error al guardar los cambios")
    },
  })

  const onSubmit = (data: CampaignFormValues) => {
    saveMutation.mutate(data)
  }

  const campaignTitle = campaign
    ? campaign.user_prompt.length > 40
      ? campaign.user_prompt.slice(0, 40) + "..."
      : campaign.user_prompt
    : "..."

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="space-y-4 pt-6">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-32 w-full" />
          </CardContent>
        </Card>
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
        <span className="text-foreground">Editar</span>
      </nav>

      <h1 className="text-2xl font-bold">Editar campaña</h1>

      <Card>
        <CardHeader>
          <CardTitle>Datos de la campaña</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* User prompt */}
            <div className="space-y-2">
              <label htmlFor="user_prompt" className="text-sm font-medium">
                Descripción de la campaña
              </label>
              <Textarea
                id="user_prompt"
                rows={6}
                placeholder="Describe tu campaña..."
                {...register("user_prompt")}
              />
              {errors.user_prompt && (
                <p className="text-sm text-destructive">
                  {errors.user_prompt.message}
                </p>
              )}
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate(`/campaigns/${campaignId}`)}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending && (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                )}
                Guardar cambios
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
