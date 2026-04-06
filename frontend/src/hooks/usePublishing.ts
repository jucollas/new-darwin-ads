import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import { toast } from "sonner"
import api, {
  getAdAccounts,
  deleteAdAccount,
  publishCampaign,
  getPublicationStatus,
  getPublications,
} from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import type { PublishRequest } from "@/types"

export function useAdAccounts() {
  return useQuery({
    queryKey: ["ad-accounts"],
    queryFn: () => getAdAccounts().then((r) => r.data.items),
  })
}

export function useDeleteAdAccount() {
  return useMutation({
    mutationFn: (id: string) => deleteAdAccount(id),
    onSuccess: () => {
      toast.success("Cuenta desconectada correctamente")
      queryClient.invalidateQueries({ queryKey: ["ad-accounts"] })
    },
    onError: () => {
      toast.error("Error al desconectar la cuenta")
    },
  })
}

export function usePublishCampaign() {
  return useMutation({
    mutationFn: async (data: PublishRequest) => {
      // Step 1: Transition campaign status to "publishing"
      await api.post(ENDPOINTS.campaigns.publish(data.campaign_id))

      try {
        // Step 2: Create the actual Meta ad via publishing-service
        const result = await publishCampaign(data).then((r) => r.data)
        return result
      } catch (error) {
        // Rollback campaign status if publishing-service fails
        await api
          .put(ENDPOINTS.campaigns.update(data.campaign_id), {
            status: "image_ready",
          })
          .catch(() => {})
        throw error
      }
    },
    onSuccess: (_data, variables) => {
      toast.success("¡Campaña enviada a publicación!")
      queryClient.invalidateQueries({ queryKey: ["campaigns"] })
      queryClient.invalidateQueries({
        queryKey: ["campaign", variables.campaign_id],
      })
      queryClient.invalidateQueries({
        queryKey: ["campaign-publication", variables.campaign_id],
      })
    },
    onError: () => {
      toast.error("Error al publicar la campaña")
    },
  })
}

export function usePublicationStatus(id: string | null) {
  return useQuery({
    queryKey: ["publication-status", id],
    queryFn: () => getPublicationStatus(id!).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "queued" || status === "publishing") return 10000
      return false
    },
  })
}

export function useCampaignPublication(campaignId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["campaign-publication", campaignId],
    queryFn: () =>
      getPublications(campaignId!).then((r) => {
        const pubs = Array.isArray(r.data) ? r.data : []
        return pubs.length > 0 ? pubs[pubs.length - 1] : null
      }),
    enabled: !!campaignId && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "queued" || status === "publishing") return 10000
      return false
    },
  })
}
