import { useQuery } from "@tanstack/react-query"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import type { Campaign, CampaignStatus } from "@/types"

export function useCampaignPolling(
  campaignId: string | null,
  targetStatus: CampaignStatus,
) {
  const query = useQuery<Campaign>({
    queryKey: ["campaign-poll", campaignId, targetStatus],
    queryFn: () =>
      api.get(ENDPOINTS.campaigns.detail(campaignId!)).then((r) => r.data),
    enabled: !!campaignId,
    refetchInterval: (query) => {
      const campaign = query.state.data
      if (!campaign) return 2000
      if (campaign.status === targetStatus || campaign.status === "failed") {
        return false
      }
      return 2000
    },
  })

  const isPolling =
    !!campaignId &&
    !!query.data &&
    query.data.status !== targetStatus &&
    query.data.status !== "failed"

  return {
    campaign: query.data ?? null,
    isPolling,
    error: query.error,
  }
}
