import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getMetricsSummary,
  getCampaignMetrics,
  getTopPerformers,
  getUnderperformers,
  triggerMetricsCollection,
} from '@/lib/api'
import { toast } from 'sonner'

export const useMetricsSummary = () =>
  useQuery({
    queryKey: ['metrics', 'summary'],
    queryFn: () => getMetricsSummary().then(r => r.data),
    staleTime: 5 * 60 * 1000,
  })

export const useCampaignMetrics = (
  campaignId: string,
  fromDate?: string,
  toDate?: string
) =>
  useQuery({
    queryKey: ['metrics', campaignId, fromDate, toDate],
    queryFn: () =>
      getCampaignMetrics(campaignId, {
        from_date: fromDate,
        to_date: toDate,
      }).then(r => r.data),
    enabled: !!campaignId,
    staleTime: 5 * 60 * 1000,
  })

export const useTopPerformers = () =>
  useQuery({
    queryKey: ['metrics', 'top-performers'],
    queryFn: () => getTopPerformers().then(r => r.data),
    staleTime: 5 * 60 * 1000,
  })

export const useUnderperformers = () =>
  useQuery({
    queryKey: ['metrics', 'underperformers'],
    queryFn: () => getUnderperformers().then(r => r.data),
    staleTime: 5 * 60 * 1000,
  })

export const useCollectMetrics = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (lookbackDays?: number) =>
      triggerMetricsCollection(lookbackDays),
    onSuccess: () => {
      toast.success('Recolección de métricas iniciada. Los datos se actualizarán pronto.')
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['metrics'] })
      }, 30000)
    },
    onError: () => {
      toast.error('Error al iniciar la recolección de métricas.')
    },
  })
}
