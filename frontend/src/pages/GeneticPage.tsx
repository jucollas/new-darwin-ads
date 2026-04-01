import { useMemo } from "react"
import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { toast } from "sonner"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import type { GeneticConfig, OptimizationRun, PaginatedResponse } from "@/types"
import {
  Play,
  Settings,
  History,
  Loader2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

const configSchema = z.object({
  min_impressions_to_evaluate: z.coerce.number().min(0),
  min_days_active: z.coerce.number().min(0),
  fitness_weights_ctr: z.coerce.number().min(0).max(1),
  fitness_weights_roas: z.coerce.number().min(0).max(1),
  fitness_weights_cpc: z.coerce.number().min(0).max(1),
  mutation_rate: z.coerce.number().min(0).max(1),
  max_active_campaigns: z.coerce.number().min(1),
})

type ConfigFormValues = z.infer<typeof configSchema>

export default function GeneticPage() {
  const { data: config, isLoading: configLoading } = useQuery<GeneticConfig>({
    queryKey: ["genetic-config"],
    queryFn: () => api.get(ENDPOINTS.optimize.config).then((r) => r.data),
  })

  const { data: runs = [], isLoading: runsLoading } = useQuery<OptimizationRun[]>({
    queryKey: ["genetic-history"],
    queryFn: () =>
      api.get(ENDPOINTS.optimize.history).then((r) => {
        const body = r.data
        if (Array.isArray(body)) return body
        return (body as PaginatedResponse<OptimizationRun>).items ?? []
      }),
  })

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ConfigFormValues>({
    resolver: zodResolver(configSchema),
    values: config
      ? {
          min_impressions_to_evaluate: config.min_impressions_to_evaluate,
          min_days_active: config.min_days_active,
          fitness_weights_ctr: config.fitness_weights.ctr,
          fitness_weights_roas: config.fitness_weights.roas,
          fitness_weights_cpc: config.fitness_weights.cpc,
          mutation_rate: config.mutation_rate,
          max_active_campaigns: config.max_active_campaigns,
        }
      : {
          min_impressions_to_evaluate: 100,
          min_days_active: 3,
          fitness_weights_ctr: 0.4,
          fitness_weights_roas: 0.4,
          fitness_weights_cpc: 0.2,
          mutation_rate: 0.1,
          max_active_campaigns: 10,
        },
  })

  const configureMutation = useMutation({
    mutationFn: (values: ConfigFormValues) =>
      api.put(ENDPOINTS.optimize.config, {
        min_impressions_to_evaluate: values.min_impressions_to_evaluate,
        min_days_active: values.min_days_active,
        fitness_weights: {
          ctr: values.fitness_weights_ctr,
          roas: values.fitness_weights_roas,
          cpc: values.fitness_weights_cpc,
        },
        mutation_rate: values.mutation_rate,
        max_active_campaigns: values.max_active_campaigns,
      }),
    onSuccess: () => {
      toast.success("Configuración guardada")
      queryClient.invalidateQueries({ queryKey: ["genetic-config"] })
    },
    onError: () => toast.error("Error al guardar configuración"),
  })

  const evaluateMutation = useMutation({
    mutationFn: () => api.post(ENDPOINTS.optimize.run),
    onSuccess: () => {
      toast.success("Evaluación completada")
      queryClient.invalidateQueries({ queryKey: ["genetic-history"] })
    },
    onError: () => toast.error("Error al ejecutar evaluación"),
  })

  const onSubmitConfig = (values: ConfigFormValues) => {
    configureMutation.mutate(values)
  }

  const isLoading = configLoading || runsLoading

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  return (
    <div className="space-y-8 p-6">
      {/* Section 1: Configuration */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <Settings className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Algoritmo Genético</h1>
            <p className="text-muted-foreground">Configuración y monitoreo</p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Configuración</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmitConfig)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="min_impressions_to_evaluate">
                Impresiones mínimas para evaluar
              </Label>
              <Input
                id="min_impressions_to_evaluate"
                type="number"
                {...register("min_impressions_to_evaluate")}
                className="max-w-xs"
              />
              <p className="text-sm text-muted-foreground">
                Campañas con menos impresiones no serán evaluadas
              </p>
              {errors.min_impressions_to_evaluate && (
                <p className="text-sm text-red-500">
                  {errors.min_impressions_to_evaluate.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="min_days_active">Días mínimos activa</Label>
              <Input
                id="min_days_active"
                type="number"
                {...register("min_days_active")}
                className="max-w-xs"
              />
              {errors.min_days_active && (
                <p className="text-sm text-red-500">
                  {errors.min_days_active.message}
                </p>
              )}
            </div>

            <Separator />

            <div className="space-y-4">
              <Label>Pesos de fitness</Label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="fitness_weights_ctr" className="text-xs">
                    CTR
                  </Label>
                  <Input
                    id="fitness_weights_ctr"
                    type="number"
                    step="0.01"
                    {...register("fitness_weights_ctr")}
                  />
                  {errors.fitness_weights_ctr && (
                    <p className="text-sm text-red-500">
                      {errors.fitness_weights_ctr.message}
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="fitness_weights_roas" className="text-xs">
                    ROAS
                  </Label>
                  <Input
                    id="fitness_weights_roas"
                    type="number"
                    step="0.01"
                    {...register("fitness_weights_roas")}
                  />
                  {errors.fitness_weights_roas && (
                    <p className="text-sm text-red-500">
                      {errors.fitness_weights_roas.message}
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="fitness_weights_cpc" className="text-xs">
                    CPC
                  </Label>
                  <Input
                    id="fitness_weights_cpc"
                    type="number"
                    step="0.01"
                    {...register("fitness_weights_cpc")}
                  />
                  {errors.fitness_weights_cpc && (
                    <p className="text-sm text-red-500">
                      {errors.fitness_weights_cpc.message}
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="mutation_rate">Tasa de mutación</Label>
              <Input
                id="mutation_rate"
                type="number"
                step="0.01"
                {...register("mutation_rate")}
                className="max-w-xs"
              />
              {errors.mutation_rate && (
                <p className="text-sm text-red-500">
                  {errors.mutation_rate.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="max_active_campaigns">
                Máximo de campañas activas
              </Label>
              <Input
                id="max_active_campaigns"
                type="number"
                {...register("max_active_campaigns")}
                className="max-w-xs"
              />
              {errors.max_active_campaigns && (
                <p className="text-sm text-red-500">
                  {errors.max_active_campaigns.message}
                </p>
              )}
            </div>

            <div className="flex gap-3">
              <Button type="submit" disabled={configureMutation.isPending}>
                {configureMutation.isPending && (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                )}
                Guardar configuración
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => evaluateMutation.mutate()}
                disabled={evaluateMutation.isPending}
              >
                {evaluateMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                Evaluar ahora
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Section 2: Optimization History */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">
              Historial de optimizaciones
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {runs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-3 font-medium text-muted-foreground">
                      Fecha
                    </th>
                    <th className="pb-3 font-medium text-muted-foreground">
                      Generación
                    </th>
                    <th className="pb-3 font-medium text-muted-foreground">
                      Evaluadas
                    </th>
                    <th className="pb-3 font-medium text-muted-foreground">
                      Duplicadas
                    </th>
                    <th className="pb-3 font-medium text-muted-foreground">
                      Eliminadas
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {runs.map((run) => (
                    <tr key={run.id}>
                      <td className="py-3 whitespace-nowrap">
                        {new Date(run.ran_at).toLocaleDateString("es-ES", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                        })}
                      </td>
                      <td className="py-3 font-mono">
                        #{run.generation_number}
                      </td>
                      <td className="py-3">{run.campaigns_evaluated}</td>
                      <td className="py-3">
                        {run.campaigns_duplicated.length}
                      </td>
                      <td className="py-3">{run.campaigns_killed.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
              <History className="h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">
                No hay optimizaciones registradas aún.
              </p>
              <p className="text-sm text-muted-foreground">
                Las optimizaciones aparecerán aquí cuando el algoritmo genético
                evalúe tus campañas.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
