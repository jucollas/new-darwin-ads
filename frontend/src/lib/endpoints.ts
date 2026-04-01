export const ENDPOINTS = {
  // campaign-service
  campaigns: {
    list: "/api/v1/campaigns",
    detail: (id: string) => `/api/v1/campaigns/${id}`,
    create: "/api/v1/campaigns",
    update: (id: string) => `/api/v1/campaigns/${id}`,
    delete: (id: string) => `/api/v1/campaigns/${id}`,
    generate: (id: string) => `/api/v1/campaigns/${id}/generate`,
    proposals: (id: string) => `/api/v1/campaigns/${id}/proposals`,
    updateProposal: (campaignId: string, proposalId: string) =>
      `/api/v1/campaigns/${campaignId}/proposals/${proposalId}`,
    selectProposal: (campaignId: string, proposalId: string) =>
      `/api/v1/campaigns/${campaignId}/select/${proposalId}`,
    publish: (id: string) => `/api/v1/campaigns/${id}/publish`,
    pause: (id: string) => `/api/v1/campaigns/${id}/pause`,
    resume: (id: string) => `/api/v1/campaigns/${id}/resume`,
  },

  // ai-generation-service (called by backend, but frontend might call for regeneration)
  ai: {
    generateProposals: "/api/v1/ai/generate/proposals",
    mutate: "/api/v1/ai/generate/mutate",
  },

  // image-generation-service
  images: {
    generate: "/api/v1/images/generate",
    detail: (id: string) => `/api/v1/images/${id}`,
    delete: (id: string) => `/api/v1/images/${id}`,
  },

  // publishing-service
  publish: {
    adAccounts: "/api/v1/publish/ad-accounts",
    adAccountDetail: (id: string) => `/api/v1/publish/ad-accounts/${id}`,
    create: "/api/v1/publish",
    publications: "/api/v1/publish/publications",
    publicationStatus: (id: string) => `/api/v1/publish/publications/${id}/status`,
    pausePublication: (id: string) => `/api/v1/publish/publications/${id}/pause`,
    resumePublication: (id: string) => `/api/v1/publish/publications/${id}/resume`,
    deletePublication: (id: string) => `/api/v1/publish/publications/${id}`,
  },

  // analytics-service
  metrics: {
    byCampaign: (campaignId: string) => `/api/v1/metrics/${campaignId}`,
    summary: "/api/v1/metrics/summary",
    topPerformers: "/api/v1/metrics/top-performers",
    underperformers: "/api/v1/metrics/underperformers",
    collect: "/api/v1/metrics/collect",
  },

  // genetic-algorithm-service
  optimize: {
    run: "/api/v1/optimize",
    history: "/api/v1/optimize",
    detail: (runId: string) => `/api/v1/optimize/${runId}`,
    config: "/api/v1/optimize/config",
  },

  // notification-service
  notifications: {
    list: "/api/v1/notifications",
    markRead: (id: string) => `/api/v1/notifications/${id}/read`,
    markAllRead: "/api/v1/notifications/read-all",
    unreadCount: "/api/v1/notifications/unread-count",
  },

  // auth (external — unchanged prefix, keep as-is)
  auth: {
    login: "/api/auth/login",
    register: "/api/auth/register",
    me: "/api/auth/me",
    profile: "/api/auth/profile",
    metaStatus: "/api/auth/meta-status",
    metaConnect: "/api/auth/meta/connect",
    metaDisconnect: "/api/auth/meta/disconnect",
  },
} as const
