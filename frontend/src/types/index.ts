// ========================
// SHARED
// ========================
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface User {
  id: string
  email: string
  name: string
  whatsapp?: string
  avatar_url?: string
}

// ========================
// CAMPAIGN SERVICE
// ========================
export interface Campaign {
  id: string
  user_id: string
  user_prompt: string
  status: CampaignStatus
  selected_proposal_id: string | null
  created_at: string
  updated_at: string
  proposals?: Proposal[]  // included when fetching detail
}

export type CampaignStatus =
  | "draft"
  | "generating"
  | "proposals_ready"
  | "image_generating"
  | "image_ready"
  | "publishing"
  | "published"
  | "paused"
  | "failed"
  | "archived"

export interface Proposal {
  id: string
  campaign_id: string
  copy_text: string
  script: string
  image_prompt: string
  target_audience: TargetAudience
  cta_type: "whatsapp_chat" | "link" | "call"
  whatsapp_number: string | null
  is_selected: boolean
  is_edited: boolean
  image_url: string | null
  created_at: string
}

export interface TargetAudience {
  age_min: number
  age_max: number
  genders: string[]
  interests: string[]
  locations: string[]
}

export interface CampaignCreateRequest {
  user_prompt: string
  whatsapp_number?: string
}

export interface ProposalUpdateRequest {
  copy_text?: string
  script?: string
  image_prompt?: string
  target_audience?: Partial<TargetAudience>
  cta_type?: "whatsapp_chat" | "link" | "call"
  whatsapp_number?: string
}

// ========================
// AI GENERATION SERVICE
// ========================
export interface GenerateProposalsRequest {
  user_prompt: string
  business_context: {
    business_name?: string
    industry?: string
    whatsapp_number?: string
  }
}

export interface GenerateProposalsResponse {
  proposals: Omit<Proposal, "id" | "campaign_id" | "is_selected" | "is_edited" | "image_url" | "created_at">[]
}

// ========================
// IMAGE GENERATION SERVICE
// ========================
export interface GenerateImageRequest {
  prompt: string
  aspect_ratio: "1:1" | "9:16"
  campaign_id: string
  proposal_id: string
}

export interface GenerateImageResponse {
  image_url: string
  storage_path: string
}

export interface ImageMetadata {
  id: string
  image_url: string
  storage_path: string
  prompt: string
  created_at: string
}

// ========================
// PUBLISHING SERVICE
// ========================
export interface AdAccount {
  id: string
  user_id: string
  meta_ad_account_id: string
  meta_page_id: string
  whatsapp_phone_number: string | null
  is_active: boolean
  created_at: string
}

export interface Publication {
  id: string
  campaign_id: string
  proposal_id: string
  ad_account_id: string
  meta_campaign_id: string | null
  meta_adset_id: string | null
  meta_ad_id: string | null
  status: PublicationStatus
  budget_daily_cents: number
  published_at: string | null
  error_message: string | null
  error_code: number | null
  created_at: string
}

export type PublicationStatus =
  | "queued"
  | "publishing"
  | "active"
  | "paused"
  | "failed"

export interface PublishRequest {
  campaign_id: string
  proposal_id: string
  ad_account_id: string
  budget_daily_cents: number
}

// ========================
// ANALYTICS SERVICE
// ========================
export interface CampaignMetric {
  id: string
  campaign_id: string
  meta_ad_id: string
  date: string
  impressions: number
  clicks: number
  spend_cents: number
  conversions: number
  ctr: number
  cpc_cents: number
  roas: number
  collected_at: string
}

export interface MetricsSummary {
  total_campaigns: number
  active_campaigns: number
  total_spend_cents: number
  total_impressions: number
  total_clicks: number
  total_conversions: number
  avg_ctr: number
  avg_cpc_cents: number
}

export interface TopPerformer {
  campaign_id: string
  meta_ad_id: string
  ctr: number
  roas: number
  spend_cents: number
  conversions: number
}

// ========================
// GENETIC ALGORITHM SERVICE
// ========================
export interface OptimizationRun {
  id: string
  user_id: string
  generation_number: number
  campaigns_evaluated: number
  campaigns_duplicated: string[]
  campaigns_killed: string[]
  fitness_scores: Record<string, number>
  ran_at: string
}

export interface GeneticConfig {
  id: string
  user_id: string
  min_impressions_to_evaluate: number
  min_days_active: number
  fitness_weights: {
    ctr: number
    roas: number
    cpc: number
  }
  mutation_rate: number
  max_active_campaigns: number
}

// ========================
// NOTIFICATION SERVICE
// ========================
export interface Notification {
  id: string
  user_id: string
  type: NotificationType
  channel: "in_app" | "email" | "whatsapp"
  title: string
  body: string
  metadata: Record<string, unknown>
  is_read: boolean
  created_at: string
}

export type NotificationType =
  | "proposals_ready"
  | "image_ready"
  | "campaign_published"
  | "campaign_failed"
  | "optimization_complete"
  | "budget_alert"
