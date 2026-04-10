import { useState } from "react"
import { RefreshCw, Pencil, Eye } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ProposalEditForm } from "@/components/ProposalEditForm"
import { ProposalDetailModal } from "@/components/ProposalDetailModal"
import { formatLocations } from "@/lib/formatters"
import type { Proposal } from "@/types"

interface ProposalCardProps {
  proposal: Proposal
  onSelect: () => void
  onRegenerate: () => void
  isRegenerating?: boolean
  index: number
  onProposalUpdated?: (updated: Proposal) => void
}

export function ProposalCard({
  proposal,
  onSelect,
  onRegenerate,
  isRegenerating = false,
  index,
  onProposalUpdated,
}: ProposalCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [currentProposal, setCurrentProposal] = useState(proposal)

  // Sync when parent updates
  if (proposal.id !== currentProposal.id) {
    setCurrentProposal(proposal)
  }

  const audience = currentProposal.target_audience
  const audienceStr = [
    audience.age_min || audience.age_max
      ? `${audience.age_min}-${audience.age_max} años`
      : null,
    audience.locations.length ? formatLocations(audience.locations) : null,
    audience.interests.length ? audience.interests.join(", ") : null,
  ]
    .filter(Boolean)
    .join(" · ")

  const handleSaved = (updated: Proposal) => {
    setCurrentProposal(updated)
    setIsEditing(false)
    onProposalUpdated?.(updated)
  }

  const handleDetailUpdated = (updated: Proposal) => {
    setCurrentProposal(updated)
    onProposalUpdated?.(updated)
  }

  return (
    <>
      <Card className="flex flex-col">
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardDescription>Propuesta #{index + 1}</CardDescription>
            {currentProposal.is_edited && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                Editada
              </Badge>
            )}
            {currentProposal.is_selected && (
              <Badge className="text-[10px] px-1.5 py-0">Seleccionada</Badge>
            )}
          </div>
          <CardTitle className="text-lg line-clamp-2">
            {currentProposal.copy_text.slice(0, 60)}...
          </CardTitle>
        </CardHeader>

        {isEditing ? (
          <CardContent>
            <ProposalEditForm
              proposal={currentProposal}
              onSaved={handleSaved}
              onCancel={() => setIsEditing(false)}
            />
          </CardContent>
        ) : (
          <>
            <CardContent className="flex-1 space-y-3">
              <div className="space-y-2 text-sm">
                <div>
                  <span className="font-medium">CTA: </span>
                  <span className="capitalize">
                    {currentProposal.cta_type}
                  </span>
                </div>
                <div>
                  <span className="font-medium">Audiencia: </span>
                  <span>{audienceStr || "Sin definir"}</span>
                </div>
              </div>

              <div className="rounded-md bg-muted p-3">
                <p className="text-xs font-medium mb-1">Copy</p>
                <p className="text-sm">{currentProposal.copy_text}</p>
              </div>

              {currentProposal.script && (
                <div className="rounded-md bg-muted p-3">
                  <p className="text-xs font-medium mb-1">Script</p>
                  <p className="text-sm">{currentProposal.script}</p>
                </div>
              )}

              {currentProposal.image_prompt && (
                <div className="rounded-md bg-muted p-3">
                  <p className="text-xs font-medium mb-1">Prompt de imagen</p>
                  <p className="text-sm">{currentProposal.image_prompt}</p>
                </div>
              )}
            </CardContent>
            <CardFooter className="gap-2 flex-wrap">
              <Button onClick={onSelect} className="flex-1">
                Elegir esta
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setDetailOpen(true)}
                title="Ver detalles"
              >
                <Eye className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setIsEditing(true)}
                title="Editar"
              >
                <Pencil className="h-4 w-4" />
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
          </>
        )}
      </Card>

      <ProposalDetailModal
        proposal={currentProposal}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onProposalUpdated={handleDetailUpdated}
      />
    </>
  )
}
