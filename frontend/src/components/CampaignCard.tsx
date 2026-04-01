import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { StatusBadge } from "@/components/StatusBadge"
import type { Campaign } from "@/types"

interface CampaignCardProps {
  campaign: Campaign
  onClick: () => void
}

export function CampaignCard({ campaign, onClick }: CampaignCardProps) {
  const formattedDate = new Date(campaign.created_at).toLocaleDateString(
    "es-ES",
    {
      year: "numeric",
      month: "short",
      day: "numeric",
    }
  )

  const title =
    campaign.user_prompt.length > 50
      ? campaign.user_prompt.slice(0, 50) + "..."
      : campaign.user_prompt

  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-md"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-lg">{title}</CardTitle>
          <StatusBadge status={campaign.status} />
        </div>
        <CardDescription className="line-clamp-2">
          {campaign.user_prompt}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{formattedDate}</span>
        </div>
      </CardContent>
    </Card>
  )
}
