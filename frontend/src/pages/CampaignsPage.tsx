import { useState, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Plus, Search, Megaphone } from "lucide-react"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/StatusBadge"
import type { Campaign, PaginatedResponse } from "@/types"

type TabFilter = "all" | "in_progress" | "published" | "paused" | "draft"

const tabs: { key: TabFilter; label: string }[] = [
  { key: "all", label: "Todas" },
  { key: "in_progress", label: "En progreso" },
  { key: "published", label: "Publicadas" },
  { key: "paused", label: "Pausadas" },
  { key: "draft", label: "Borradores" },
]

const inProgressStatuses = new Set([
  "generating",
  "proposals_ready",
  "image_generating",
  "image_ready",
  "publishing",
])

export default function CampaignsPage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabFilter>("all")
  const [search, setSearch] = useState("")

  const campaignsQuery = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn: () =>
      api.get(ENDPOINTS.campaigns.list).then((r) => {
        const body = r.data
        if (Array.isArray(body)) return body
        return (body as PaginatedResponse<Campaign>).items ?? []
      }),
  })

  const filteredCampaigns = useMemo(() => {
    if (!campaignsQuery.data) return []
    let list = campaignsQuery.data

    if (activeTab === "in_progress") {
      list = list.filter((c) => inProgressStatuses.has(c.status))
    } else if (activeTab !== "all") {
      list = list.filter((c) => c.status === activeTab)
    }

    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter((c) => c.user_prompt.toLowerCase().includes(q))
    }

    return list
  }, [campaignsQuery.data, activeTab, search])

  const getCampaignTitle = (campaign: Campaign) => {
    return campaign.user_prompt.length > 50
      ? campaign.user_prompt.slice(0, 50) + "..."
      : campaign.user_prompt
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-3xl font-bold">Mis Campañas</h1>
        <Button onClick={() => navigate("/campaigns/new")}>
          <Plus className="mr-2 h-4 w-4" />
          Nueva Campaña
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        {/* Tabs */}
        <div className="flex gap-1 rounded-lg border p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar campaña..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Campaign grid */}
      {campaignsQuery.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-full mt-2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-1/2" />
              </CardContent>
              <CardFooter>
                <Skeleton className="h-6 w-16" />
              </CardFooter>
            </Card>
          ))}
        </div>
      ) : filteredCampaigns.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16">
          <div className="rounded-full bg-muted p-4 mb-4">
            <Megaphone className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-1">
            No tienes campañas aún
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Crea tu primera campaña con ayuda de la IA
          </p>
          <Button onClick={() => navigate("/campaigns/new")}>
            <Plus className="mr-2 h-4 w-4" />
            Crear mi primera campaña
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCampaigns.map((campaign) => (
            <Card
              key={campaign.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => navigate(`/campaigns/${campaign.id}`)}
            >
              <CardHeader>
                <CardTitle className="text-lg">{getCampaignTitle(campaign)}</CardTitle>
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {campaign.user_prompt}
                </p>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <StatusBadge status={campaign.status} />
                </div>
              </CardContent>
              <CardFooter className="justify-between">
                <span className="text-xs text-muted-foreground">
                  {new Date(campaign.updated_at).toLocaleDateString("es-ES", {
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
