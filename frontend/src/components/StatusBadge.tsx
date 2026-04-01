import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { CampaignStatus, PublicationStatus } from "@/types"

type Status = CampaignStatus | PublicationStatus

interface StatusBadgeProps {
  status: Status
}

const statusConfig: Record<Status, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "Borrador", variant: "outline" },
  generating: { label: "Generando...", variant: "secondary" },
  proposals_ready: { label: "Propuestas listas", variant: "default" },
  image_generating: { label: "Generando imagen...", variant: "secondary" },
  image_ready: { label: "Imagen lista", variant: "default" },
  publishing: { label: "Publicando...", variant: "secondary" },
  published: { label: "Publicada", variant: "default" },
  active: { label: "Activa", variant: "default" },
  paused: { label: "Pausada", variant: "secondary" },
  failed: { label: "Error", variant: "destructive" },
  archived: { label: "Archivada", variant: "outline" },
  queued: { label: "En cola", variant: "outline" },
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] ?? { label: status, variant: "outline" as const }

  return (
    <Badge variant={config.variant}>
      {config.label}
    </Badge>
  )
}
