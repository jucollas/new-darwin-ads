import { Link } from "react-router-dom"
import { Users, Image, Type, MessageSquare, HelpCircle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { formatMutationField, formatROAS, formatFitnessScore } from "@/lib/formatters"
import type { DuplicatedCampaign, CampaignFitnessScore } from "@/types"

const MUTATION_ICONS: Record<string, React.ElementType> = {
  Users,
  Image,
  Type,
  MessageSquare,
  HelpCircle,
}

interface DuplicatedCampaignCardProps {
  duplicated: DuplicatedCampaign
  parentFitness: CampaignFitnessScore | undefined
  getName: (id: string) => string
}

export default function DuplicatedCampaignCard({
  duplicated,
  parentFitness,
  getName,
}: DuplicatedCampaignCardProps) {
  const mutation = formatMutationField(duplicated.mutation_field)
  const MutIcon = MUTATION_ICONS[mutation.iconName] ?? HelpCircle

  return (
    <Card className="border-green-200 bg-green-50/30">
      <CardContent className="pt-4 space-y-3">
        <p className="font-medium text-sm">
          Nueva variante de &quot;{getName(duplicated.parent_id)}&quot;
        </p>

        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            <MutIcon className="h-3 w-3 mr-1" />
            {mutation.label}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {mutation.description}
          </span>
        </div>

        {parentFitness && (
          <div className="flex gap-4 text-xs text-muted-foreground pt-1">
            <span>
              ROAS original:{" "}
              <span className="font-medium text-foreground">
                {formatROAS(parentFitness.raw_scores?.roas).text}
              </span>
            </span>
            <span>
              Puntuación:{" "}
              <span className="font-medium text-foreground">
                {formatFitnessScore(parentFitness.final_score).label}
              </span>
            </span>
          </div>
        )}

        <div className="flex gap-4 text-xs pt-2 border-t">
          <Link
            to={`/campaigns/${duplicated.parent_id}`}
            className="text-primary hover:underline"
          >
            Ver campaña original &rarr;
          </Link>
          <Link
            to={`/campaigns/${duplicated.new_campaign_id}`}
            className="text-primary hover:underline"
          >
            Ver nueva variante &rarr;
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
