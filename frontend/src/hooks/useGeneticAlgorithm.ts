import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { geneticApi, getMetricsSummary, getTopPerformers } from "@/lib/api"
import { toast } from "sonner"
import type {
  OptimizationRun,
  GeneticConfig,
  GeneticConfigUpdate,
  MetricsSummary,
  TopPerformer,
  PaginatedResponse,
} from "@/types"

// ---- Genetic Algorithm Queries ----

export const useOptimizationRuns = (page = 1, pageSize = 10) =>
  useQuery({
    queryKey: ["optimization-runs", page, pageSize],
    queryFn: () =>
      geneticApi.listRuns(page, pageSize).then((r) => {
        const body = r.data
        if (Array.isArray(body)) return body as OptimizationRun[]
        return (body as PaginatedResponse<OptimizationRun>).items ?? []
      }),
    refetchInterval: 60_000,
  })

export const useOptimizationRunDetail = (runId: string | undefined) =>
  useQuery({
    queryKey: ["optimization-run", runId],
    queryFn: () => geneticApi.getRunDetail(runId!).then((r) => r.data),
    enabled: !!runId,
  })

export const useGeneticConfig = () =>
  useQuery<GeneticConfig>({
    queryKey: ["genetic-config"],
    queryFn: () => geneticApi.getConfig().then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })

// ---- Analytics Queries (defensive) ----

export const useMetricsSummaryGenetic = () =>
  useQuery<MetricsSummary>({
    queryKey: ["metrics", "summary"],
    queryFn: () =>
      getMetricsSummary().then((r) => {
        const data = r.data
        return (data as MetricsSummary) ?? {}
      }),
    refetchInterval: 5 * 60 * 1000,
  })

export const useTopPerformersGenetic = () =>
  useQuery<TopPerformer[]>({
    queryKey: ["metrics", "top-performers"],
    queryFn: () =>
      getTopPerformers().then((r) => {
        const data = r.data
        if (Array.isArray(data)) return data
        if (data && typeof data === "object" && "items" in data)
          return (data as { items: TopPerformer[] }).items ?? []
        return []
      }),
    refetchInterval: 5 * 60 * 1000,
  })

// ---- Mutations ----

export const useTriggerOptimization = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => geneticApi.triggerOptimization(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["optimization-runs"] })
      toast.success("Optimización completada")
    },
    onError: (error: unknown) => {
      const msg =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Error al ejecutar la optimización"
      toast.error(msg)
    },
  })
}

export const useUpdateGeneticConfig = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: GeneticConfigUpdate) => geneticApi.updateConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["genetic-config"] })
      toast.success("Configuración guardada. Los cambios aplican en la próxima optimización.")
    },
    onError: () => {
      toast.error("Error al guardar la configuración")
    },
  })
}
