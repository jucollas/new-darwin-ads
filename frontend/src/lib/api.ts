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
import type { AdAccount, PaginatedResponse, Publication, PublishRequest } from "@/types"

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
