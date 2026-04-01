import { useNavigate, useParams, Link } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { toast } from "sonner"
import type { Publication } from "@/types"
import { Loader2, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useState, useEffect } from "react"

export default function PublicationEditPage() {
  const { publicationId } = useParams<{ publicationId: string }>()
  const navigate = useNavigate()

  const [budgetDollars, setBudgetDollars] = useState("")

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

  useEffect(() => {
    if (publication) {
      setBudgetDollars((publication.budget_daily_cents / 100).toFixed(2))
    }
  }, [publication])

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put(ENDPOINTS.publish.publicationStatus(publicationId!), {
        budget_daily_cents: Math.round(Number(budgetDollars) * 100),
      }),
    onSuccess: () => {
      toast.success("Cambios guardados exitosamente")
      queryClient.invalidateQueries({
        queryKey: ["publication", publicationId],
      })
      navigate(`/publications/${publicationId}`)
    },
    onError: () => toast.error("Error al guardar los cambios"),
  })

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[300px]" />
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

  return (
    <div className="space-y-8 p-6 max-w-2xl mx-auto">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-muted-foreground">
        <Link
          to="/campaigns"
          className="hover:text-foreground transition-colors"
        >
          Campañas
        </Link>
        <ChevronRight className="h-4 w-4" />
        <Link
          to={`/publications/${publicationId}`}
          className="hover:text-foreground transition-colors"
        >
          Publicación
        </Link>
        <ChevronRight className="h-4 w-4" />
        <span className="text-foreground font-medium">Editar</span>
      </nav>

      <h1 className="text-2xl font-bold">Editar publicación</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Presupuesto</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="budgetDollars">Presupuesto diario ($)</Label>
            <Input
              id="budgetDollars"
              type="number"
              step="0.01"
              min={0}
              value={budgetDollars}
              onChange={(e) => setBudgetDollars(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending && (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          )}
          Guardar cambios
        </Button>
        <Button type="button" variant="outline" onClick={() => navigate(-1)}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}
