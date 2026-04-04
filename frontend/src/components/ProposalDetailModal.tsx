import { useState, useEffect, useRef, useCallback } from "react"
import { useMutation } from "@tanstack/react-query"
import {
  Pencil,
  RefreshCw,
  Loader2,
  ImageIcon,
} from "lucide-react"
import { toast } from "sonner"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { queryClient } from "@/lib/queryClient"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ProposalEditForm } from "@/components/ProposalEditForm"
import type { Proposal, Campaign } from "@/types"

interface ProposalDetailModalProps {
  proposal: Proposal | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onProposalUpdated?: (updated: Proposal) => void
}

const CTA_LABELS: Record<string, string> = {
  whatsapp_chat: "WhatsApp Chat",
  link: "Link",
  call: "Llamada",
}

const POLL_INTERVAL = 5000
const POLL_TIMEOUT = 120000

export function ProposalDetailModal({
  proposal,
  open,
  onOpenChange,
  onProposalUpdated,
}: ProposalDetailModalProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [showRegenConfirm, setShowRegenConfirm] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [currentProposal, setCurrentProposal] = useState<Proposal | null>(
    proposal,
  )
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollStartRef = useRef<number>(0)

  // Sync currentProposal when prop changes
  useEffect(() => {
    setCurrentProposal(proposal)
  }, [proposal])

  // Reset state when modal closes
  useEffect(() => {
    if (!open) {
      setIsEditing(false)
      setShowRegenConfirm(false)
      stopPolling()
    }
  }, [open])

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  const regenerateMutation = useMutation({
    mutationFn: async () => {
      if (!currentProposal) throw new Error("No proposal")
      await api.post(
        ENDPOINTS.campaigns.selectProposal(
          currentProposal.campaign_id,
          currentProposal.id,
        ),
      )
    },
    onSuccess: () => {
      setIsRegenerating(true)
      setShowRegenConfirm(false)
      startPolling()
    },
    onError: () => {
      toast.error("Error al regenerar la imagen")
    },
  })

  const startPolling = () => {
    if (!currentProposal) return
    pollStartRef.current = Date.now()

    pollTimerRef.current = setInterval(async () => {
      const elapsed = Date.now() - pollStartRef.current

      if (elapsed >= POLL_TIMEOUT) {
        stopPolling()
        setIsRegenerating(false)
        toast.error(
          "La generación de imagen está tardando más de lo esperado. Recarga la página.",
        )
        return
      }

      try {
        const { data: campaign } = await api.get<Campaign>(
          ENDPOINTS.campaigns.detail(currentProposal.campaign_id),
        )

        if (campaign.status === "image_ready") {
          stopPolling()
          // Fetch updated proposals to get new image_url
          const { data } = await api.get(
            ENDPOINTS.campaigns.proposals(currentProposal.campaign_id),
          )
          const items: Proposal[] = Array.isArray(data)
            ? data
            : data.items ?? []
          const updated = items.find((p) => p.id === currentProposal.id)
          if (updated) {
            setCurrentProposal(updated)
            onProposalUpdated?.(updated)
          }
          setIsRegenerating(false)
          queryClient.invalidateQueries({
            queryKey: ["campaign-proposals", currentProposal.campaign_id],
          })
          queryClient.invalidateQueries({
            queryKey: ["campaign", currentProposal.campaign_id],
          })
          toast.success("Imagen regenerada exitosamente")
        } else if (campaign.status === "failed") {
          stopPolling()
          setIsRegenerating(false)
          toast.error("Error al generar la imagen")
        }
      } catch {
        // Ignore polling errors, retry on next interval
      }
    }, POLL_INTERVAL)
  }

  const handleSaved = (updated: Proposal) => {
    setCurrentProposal(updated)
    setIsEditing(false)
    onProposalUpdated?.(updated)
  }

  if (!currentProposal) return null

  const audience = currentProposal.target_audience

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              Detalle de propuesta
              {currentProposal.is_selected && (
                <Badge>Seleccionada</Badge>
              )}
              {currentProposal.is_edited && (
                <Badge variant="secondary">Editada</Badge>
              )}
            </DialogTitle>
            <DialogDescription>
              Creada el{" "}
              {new Date(currentProposal.created_at).toLocaleDateString(
                "es-ES",
                {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                },
              )}
            </DialogDescription>
          </DialogHeader>

          {isEditing ? (
            <ProposalEditForm
              proposal={currentProposal}
              onSaved={handleSaved}
              onCancel={() => setIsEditing(false)}
            />
          ) : (
            <div className="space-y-4">
              {/* Image */}
              <div className="rounded-lg border overflow-hidden">
                {isRegenerating ? (
                  <div className="flex flex-col items-center justify-center py-16 bg-muted/30">
                    <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
                    <p className="text-sm font-medium">
                      Generando nueva imagen...
                    </p>
                  </div>
                ) : currentProposal.image_url ? (
                  <img
                    src={currentProposal.image_url}
                    alt="Imagen de la propuesta"
                    className="w-full object-contain max-h-96"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 bg-muted/30">
                    <ImageIcon className="h-10 w-10 text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                      Imagen no generada aún
                    </p>
                  </div>
                )}
              </div>

              {/* Regenerate button */}
              {currentProposal.image_url && !isRegenerating && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowRegenConfirm(true)}
                >
                  <RefreshCw className="mr-1 h-4 w-4" />
                  Regenerar imagen
                </Button>
              )}

              {/* Copy text */}
              <div className="space-y-1">
                <p className="text-sm font-medium">Copy</p>
                <p className="text-sm whitespace-pre-wrap">
                  {currentProposal.copy_text}
                </p>
              </div>

              {/* Script */}
              <div className="space-y-1">
                <p className="text-sm font-medium">Script</p>
                <p className="text-sm whitespace-pre-wrap">
                  {currentProposal.script}
                </p>
              </div>

              {/* Image prompt */}
              <div className="space-y-1">
                <p className="text-sm font-medium">Prompt de imagen</p>
                <div className="rounded-md bg-muted p-3">
                  <p className="text-sm font-mono">
                    {currentProposal.image_prompt}
                  </p>
                </div>
              </div>

              {/* Target audience */}
              <div className="space-y-1">
                <p className="text-sm font-medium">Audiencia objetivo</p>
                <div className="text-sm space-y-0.5">
                  <p>
                    Edades {audience.age_min}–{audience.age_max}
                  </p>
                  <p>
                    Géneros:{" "}
                    {audience.genders
                      .map((g) =>
                        g === "male"
                          ? "Masculino"
                          : g === "female"
                            ? "Femenino"
                            : "Todos",
                      )
                      .join(", ")}
                  </p>
                  <p>Intereses: {audience.interests.join(", ")}</p>
                  <p>Ubicaciones: {audience.locations.join(", ")}</p>
                </div>
              </div>

              {/* CTA */}
              <div className="space-y-1">
                <p className="text-sm font-medium">Tipo de CTA</p>
                <p className="text-sm">
                  {CTA_LABELS[currentProposal.cta_type] ??
                    currentProposal.cta_type}
                </p>
              </div>

              {/* WhatsApp number */}
              {currentProposal.cta_type === "whatsapp_chat" &&
                currentProposal.whatsapp_number && (
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Número de WhatsApp</p>
                    <p className="text-sm">
                      {currentProposal.whatsapp_number}
                    </p>
                  </div>
                )}

              {/* Edit button */}
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setIsEditing(true)}
                  disabled={isRegenerating}
                >
                  <Pencil className="mr-1 h-4 w-4" />
                  Editar
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Regenerate confirmation dialog */}
      <Dialog open={showRegenConfirm} onOpenChange={setShowRegenConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Regenerar imagen</DialogTitle>
            <DialogDescription>
              ¿Estás seguro de que quieres regenerar la imagen? La imagen actual
              será reemplazada.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowRegenConfirm(false)}
            >
              Cancelar
            </Button>
            <Button
              onClick={() => regenerateMutation.mutate()}
              disabled={regenerateMutation.isPending}
            >
              {regenerateMutation.isPending && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
              )}
              Confirmar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
