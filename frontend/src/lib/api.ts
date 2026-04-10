import axios from "axios"

const api = axios.create({
  baseURL: import.meta.env.VITE_API_GATEWAY || "",
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token")
      window.location.href = "/login"
    }
    return Promise.reject(error)
  },
)

export default api

// ========================
// PUBLISHING SERVICE
// ========================
import { ENDPOINTS } from "./endpoints"
import type {
  AdAccount,
  GeneticConfig,
  GeneticConfigUpdate,
  MetricListResponse,
  MetricsSummary,
  OptimizationRun,
  PaginatedResponse,
  Publication,
  PublishRequest,
  TopPerformer,
} from "@/types"

export const getMetaLoginUrl = () =>
  api.get<{ login_url: string }>(ENDPOINTS.publish.metaLoginUrl)

export const getAdAccounts = () =>
  api.get<PaginatedResponse<AdAccount>>(ENDPOINTS.publish.adAccounts)

export const deleteAdAccount = (id: string) =>
  api.delete(ENDPOINTS.publish.adAccountDetail(id))

export const publishCampaign = (data: PublishRequest) =>
  api.post<Publication>(ENDPOINTS.publish.create, data)

export const getPublicationStatus = (id: string) =>
  api.get<Publication>(ENDPOINTS.publish.publicationStatus(id))

export const getPublications = (campaignId: string) =>
  api
    .get<PaginatedResponse<Publication>>(ENDPOINTS.publish.publications)
    .then((r) => ({
      ...r,
      data: r.data.items.filter((p) => p.campaign_id === campaignId),
    }))

export const pausePublication = (id: string) =>
  api.post(ENDPOINTS.publish.pausePublication(id))

export const resumePublication = (id: string) =>
  api.post(ENDPOINTS.publish.resumePublication(id))

export const verifyAdAccount = (id: string) =>
  api.get<{
    is_valid: boolean
    message?: string
    expires_at?: string | null
    scopes?: string[]
    needs_reauth?: boolean
  }>(`${ENDPOINTS.publish.adAccountDetail(id)}/verify`)

// ========================
// ANALYTICS SERVICE
// ========================
export const getMetricsSummary = () =>
  api.get<MetricsSummary>(ENDPOINTS.metrics.summary)

export const getCampaignMetrics = (
  campaignId: string,
  params?: { from_date?: string; to_date?: string }
) => api.get<MetricListResponse>(ENDPOINTS.metrics.byCampaign(campaignId), { params })

export const getTopPerformers = () =>
  api.get<TopPerformer[]>(ENDPOINTS.metrics.topPerformers)

export const getUnderperformers = () =>
  api.get<TopPerformer[]>(ENDPOINTS.metrics.underperformers)

export const triggerMetricsCollection = (lookbackDays: number = 7) =>
  api.post(ENDPOINTS.metrics.collect, { lookback_days: lookbackDays })

// ========================
// GENETIC ALGORITHM API
// ========================

export const geneticApi = {
  listRuns: (page = 1, pageSize = 10) =>
    api.get<PaginatedResponse<OptimizationRun>>(ENDPOINTS.optimize.history, {
      params: { page, page_size: pageSize },
    }),

  getRunDetail: (runId: string) =>
    api.get<OptimizationRun>(ENDPOINTS.optimize.detail(runId)),

  triggerOptimization: () =>
    api.post<OptimizationRun>(ENDPOINTS.optimize.run),

  getConfig: () =>
    api.get<GeneticConfig>(ENDPOINTS.optimize.config),

  updateConfig: (data: GeneticConfigUpdate) =>
    api.put<GeneticConfig>(ENDPOINTS.optimize.config, data),
}
