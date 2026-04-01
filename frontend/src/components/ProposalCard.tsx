import { RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { Proposal } from "@/types"

interface ProposalCardProps {
  proposal: Proposal
  onSelect: () => void
  onRegenerate: () => void
  isRegenerating?: boolean
  index: number
}

export function ProposalCard({
  proposal,
  onSelect,
  onRegenerate,
  isRegenerating = false,
  index,
}: ProposalCardProps) {
  const audience = proposal.target_audience
  const audienceStr = [
    audience.age_min || audience.age_max
      ? `${audience.age_min}-${audience.age_max} años`
      : null,
    audience.locations.length ? audience.locations.join(", ") : null,
    audience.interests.length ? audience.interests.join(", ") : null,
  ]
    .filter(Boolean)
    .join(" · ")

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardDescription>Propuesta #{index + 1}</CardDescription>
        <CardTitle className="text-lg line-clamp-2">
          {proposal.copy_text.slice(0, 60)}...
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 space-y-3">
        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium">CTA: </span>
            <span className="capitalize">{proposal.cta_type}</span>
          </div>
          <div>
            <span className="font-medium">Audiencia: </span>
            <span>{audienceStr || "Sin definir"}</span>
          </div>
        </div>

        <div className="rounded-md bg-muted p-3">
          <p className="text-xs font-medium mb-1">Copy</p>
          <p className="text-sm">{proposal.copy_text}</p>
        </div>

        {proposal.script && (
          <div className="rounded-md bg-muted p-3">
            <p className="text-xs font-medium mb-1">Script</p>
            <p className="text-sm">{proposal.script}</p>
          </div>
        )}

        {proposal.image_prompt && (
          <div className="rounded-md bg-muted p-3">
            <p className="text-xs font-medium mb-1">Prompt de imagen</p>
            <p className="text-sm">{proposal.image_prompt}</p>
          </div>
        )}
      </CardContent>
      <CardFooter className="gap-2">
        <Button onClick={onSelect} className="flex-1">
          Elegir esta
        </Button>
        <Button
          variant="ghost"
          onClick={onRegenerate}
          disabled={isRegenerating}
        >
          <RefreshCw
            className={`h-4 w-4 mr-1 ${isRegenerating ? "animate-spin" : ""}`}
          />
          Regenerar
        </Button>
      </CardFooter>
    </Card>
  )
}
