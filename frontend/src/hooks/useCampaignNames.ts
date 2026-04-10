import { useMemo, useCallback } from "react"
import { useQueries } from "@tanstack/react-query"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import type { Campaign } from "@/types"

export function useCampaignNames(campaignIds: string[]) {
  const uniqueIds = useMemo(
    () => [...new Set(campaignIds.filter(Boolean))],
    [campaignIds]
  )

  const queries = useQueries({
    queries: uniqueIds.map((id) => ({
      queryKey: ["campaign", id],
      queryFn: () =>
        api
          .get<Campaign>(ENDPOINTS.campaigns.detail(id))
          .then((r) => r.data)
          .catch(() => null),
      staleTime: 10 * 60 * 1000,
      retry: 1,
    })),
  })

  // Derive a stable key from query results to avoid recomputing every render
  const resultKey = queries.map((q) => q.dataUpdatedAt).join(",")

  const nameMap = useMemo(() => {
    const map = new Map<string, string>()
    uniqueIds.forEach((id, i) => {
      const data = queries[i]?.data
      if (data) {
        const name = data.user_prompt ?? ""
        map.set(id, name.length > 50 ? name.slice(0, 47) + "..." : name || "Campaña sin nombre")
      } else if (queries[i]?.isError) {
        map.set(id, "Campaña desconocida")
      }
    })
    return map
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uniqueIds, resultKey])

  const getName = useCallback(
    (id: string): string => nameMap.get(id) ?? "Campaña sin nombre",
    [nameMap]
  )

  const isLoading = queries.some((q) => q.isLoading)

  return { getName, isLoading }
}
