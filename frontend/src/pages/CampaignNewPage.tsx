import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useMutation } from "@tanstack/react-query"
import {
  Sparkles,
  Check,
  ArrowLeft,
  Loader2,
  Phone,
  RefreshCw,
  Dna,
  Image as ImageIcon,
} from "lucide-react"
import { toast } from "sonner"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { queryClient } from "@/lib/queryClient"
import { useCampaignPolling } from "@/hooks/useCampaignPolling"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ProposalCard } from "@/components/ProposalCard"
import type { Campaign, Proposal, CampaignStatus } from "@/types"

type Step = 1 | 2 | 3

export default function CampaignNewPage() {
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>(1)
  const [prompt, setPrompt] = useState("")
  const [campaignId, setCampaignId] = useState<string | null>(null)
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null)
  const [regeneratingIdx, setRegeneratingIdx] = useState<number | null>(null)

  // Editable field for step 3
  const [editWhatsapp, setEditWhatsapp] = useState("")

  // Polling target status changes depending on the step
  const [pollTarget, setPollTarget] = useState<CampaignStatus>("proposals_ready")

  const { campaign: polledCampaign, isPolling } = useCampaignPolling(
    campaignId,
    pollTarget,
  )

  // When polling resolves to proposals_ready, fetch proposals and advance
  const handlePollComplete = async (campaign: Campaign) => {
    if (campaign.status === "proposals_ready" && step === 1) {
      try {
        const { data } = await api.get(ENDPOINTS.campaigns.proposals(campaign.id))
        const items: Proposal[] = Array.isArray(data) ? data : data.items ?? []
        setProposals(items)
        setStep(2)
      } catch {
        toast.error("Error al obtener las propuestas")
      }
    } else if (campaign.status === "image_ready" && step === 2) {
      // Refresh proposals to get image_url
      try {
        const { data } = await api.get(ENDPOINTS.campaigns.proposals(campaign.id))
        const items: Proposal[] = Array.isArray(data) ? data : data.items ?? []
        const selected = items.find((p) => p.is_selected) ?? null
        if (selected) {
          setSelectedProposal(selected)
          setEditWhatsapp(selected.whatsapp_number ?? "")
        }
        setProposals(items)
        setStep(3)
      } catch {
        toast.error("Error al obtener la propuesta seleccionada")
      }
    } else if (campaign.status === "failed") {
      toast.error("Hubo un error en el procesamiento de la campaña")
    }
  }

  // Watch polling results
  if (polledCampaign && !isPolling) {
    if (
      (polledCampaign.status === "proposals_ready" && step === 1 && proposals.length === 0) ||
      (polledCampaign.status === "image_ready" && step === 2 && !selectedProposal)
    ) {
      handlePollComplete(polledCampaign)
    }
  }

  // Step 1: Create campaign + trigger generation
  const generateMutation = useMutation({
    mutationFn: async (userPrompt: string) => {
      // Create campaign first
      const { data: campaign } = await api.post(ENDPOINTS.campaigns.create, {
        user_prompt: userPrompt,
      })
      setCampaignId(campaign.id)
      // Trigger AI generation
      await api.post(ENDPOINTS.campaigns.generate(campaign.id))
      setPollTarget("proposals_ready")
      return campaign
    },
    onError: (err: any) => {
      toast.error(
        err?.response?.data?.detail || "Error al generar propuestas"
      )
    },
  })

  // Regenerate proposals
  const handleRegenerate = async (index: number) => {
    if (!campaignId) return
    setRegeneratingIdx(index)
    try {
      await api.post(ENDPOINTS.campaigns.generate(campaignId))
      // Poll until proposals_ready again
      setProposals([])
      setPollTarget("proposals_ready")
      setStep(1) // Go back to polling state visually
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail || "Error al regenerar propuestas"
      )
    } finally {
      setRegeneratingIdx(null)
    }
  }

  // Step 2 -> 3: Select proposal (triggers image generation)
  const selectMutation = useMutation({
    mutationFn: async (proposal: Proposal) => {
      await api.post(
        ENDPOINTS.campaigns.selectProposal(campaignId!, proposal.id),
      )
      setSelectedProposal(proposal)
      setPollTarget("image_ready")
    },
    onError: (err: any) => {
      toast.error(
        err?.response?.data?.detail || "Error al seleccionar propuesta"
      )
    },
  })

  // Step 3: Publish campaign
  const publishMutation = useMutation({
    mutationFn: async () => {
      // Update whatsapp on proposal if changed
      if (editWhatsapp && selectedProposal) {
        await api.put(
          ENDPOINTS.campaigns.updateProposal(campaignId!, selectedProposal.id),
          { whatsapp_number: editWhatsapp },
        )
      }
      await api.post(ENDPOINTS.campaigns.publish(campaignId!))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaigns"] })
      toast.success("Campaña publicada exitosamente")
      navigate(`/campaigns/${campaignId}`)
    },
    onError: (err: any) => {
      toast.error(
        err?.response?.data?.detail || "Error al publicar la campaña"
      )
    },
  })

  const selectProposal = (proposal: Proposal) => {
    selectMutation.mutate(proposal)
  }

  const formatAudience = (p: Proposal) => {
    const ta = p.target_audience
    const parts: string[] = []
    if (ta.age_min || ta.age_max) parts.push(`${ta.age_min}-${ta.age_max} años`)
    if (ta.genders.length) parts.push(ta.genders.join(", "))
    if (ta.locations.length) parts.push(ta.locations.join(", "))
    if (ta.interests.length) parts.push(ta.interests.join(", "))
    return parts.join(" · ") || "Sin definir"
  }

  const isWaitingForProposals = isPolling && pollTarget === "proposals_ready"
  const isWaitingForImage = isPolling && pollTarget === "image_ready"

  // Loading timeout feedback
  const [waitingSeconds, setWaitingSeconds] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (isWaitingForProposals || generateMutation.isPending) {
      setWaitingSeconds(0)
      timerRef.current = setInterval(() => setWaitingSeconds((s) => s + 1), 1000)
    } else {
      setWaitingSeconds(0)
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isWaitingForProposals, generateMutation.isPending])

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Step indicators */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className={step >= 1 ? "text-primary font-medium" : ""}>
          1. Describe
        </span>
        <span>/</span>
        <span className={step >= 2 ? "text-primary font-medium" : ""}>
          2. Elige
        </span>
        <span>/</span>
        <span className={step >= 3 ? "text-primary font-medium" : ""}>
          3. Confirma
        </span>
      </div>

      {/* STEP 1 */}
      {step === 1 && (
        <div className="space-y-4">
          <div>
            <h1 className="text-3xl font-bold">Crear nueva campaña</h1>
            <p className="text-muted-foreground mt-1">
              Describe en lenguaje natural la campaña que quieres y la IA
              generará propuestas para ti
            </p>
          </div>

          <Textarea
            placeholder="Describe tu campaña... ej: Quiero una campaña para promocionar mi restaurante de comida italiana en Miami, orientada a parejas jóvenes, con un presupuesto de $10 diarios"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={6}
            className="resize-none"
            disabled={generateMutation.isPending || isWaitingForProposals}
          />

          <Button
            onClick={() => generateMutation.mutate(prompt)}
            disabled={!prompt.trim() || generateMutation.isPending || isWaitingForProposals}
            className="w-full sm:w-auto"
          >
            {generateMutation.isPending || isWaitingForProposals ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Generar propuestas con IA
          </Button>

          {/* AI loading state */}
          {(generateMutation.isPending || isWaitingForProposals) && (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12">
                {waitingSeconds < 60 ? (
                  <>
                    <Dna className="h-10 w-10 text-primary animate-spin mb-4" />
                    <p className="text-sm font-medium">
                      La IA está generando propuestas...
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {waitingSeconds > 30
                        ? "La IA está tardando más de lo esperado. Por favor espera..."
                        : "Esto puede tomar unos segundos"}
                    </p>
                  </>
                ) : (
                  <>
                    <Dna className="h-10 w-10 text-destructive mb-4" />
                    <p className="text-sm font-medium">
                      Hubo un problema. Intenta generar de nuevo.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3"
                      onClick={() => {
                        if (campaignId) {
                          handleRegenerate(0)
                        }
                      }}
                    >
                      <RefreshCw className="mr-2 h-3.5 w-3.5" />
                      Reintentar
                    </Button>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* STEP 2 */}
      {step === 2 && (
        <div className="space-y-4">
          <div>
            <h1 className="text-3xl font-bold">Elige una propuesta</h1>
            <p className="text-muted-foreground mt-1">
              Selecciona la propuesta que más te guste o regenera las que no
              te convenzan
            </p>
          </div>

          {/* Waiting for image generation */}
          {isWaitingForImage && (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <ImageIcon className="h-10 w-10 text-primary animate-pulse mb-4" />
                <p className="text-sm font-medium">
                  Generando imagen para la propuesta seleccionada...
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Esto puede tomar unos segundos
                </p>
              </CardContent>
            </Card>
          )}

          {!isWaitingForImage && (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                {proposals.map((proposal, index) => (
                  <ProposalCard
                    key={proposal.id}
                    proposal={proposal}
                    index={index}
                    onSelect={() => selectProposal(proposal)}
                    onRegenerate={() => handleRegenerate(index)}
                    isRegenerating={regeneratingIdx === index}
                    onProposalUpdated={(updated) => {
                      setProposals((prev) =>
                        prev.map((p) => (p.id === updated.id ? updated : p)),
                      )
                    }}
                  />
                ))}
              </div>

              <button
                onClick={() => {
                  setStep(1)
                  setProposals([])
                  setCampaignId(null)
                }}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="inline mr-1 h-3.5 w-3.5" />
                Ninguna me convence, volver
              </button>
            </>
          )}
        </div>
      )}

      {/* STEP 3 */}
      {step === 3 && selectedProposal && (
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold">Confirmar y publicar campaña</h1>
            <p className="text-muted-foreground mt-1">
              Revisa los datos y ajusta lo que necesites antes de publicar
            </p>
          </div>

          {/* Image preview */}
          {selectedProposal.image_url && (
            <Card>
              <CardContent className="p-4">
                <img
                  src={selectedProposal.image_url}
                  alt="Imagen generada"
                  className="w-full max-h-80 object-contain rounded-lg"
                />
              </CardContent>
            </Card>
          )}

          {/* Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Resumen de la propuesta
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div>
                <span className="font-medium">Copy: </span>
                {selectedProposal.copy_text}
              </div>
              <div>
                <span className="font-medium">Script: </span>
                {selectedProposal.script}
              </div>
              <div>
                <span className="font-medium">CTA: </span>
                {selectedProposal.cta_type}
              </div>
              <div>
                <span className="font-medium">Audiencia: </span>
                {formatAudience(selectedProposal)}
              </div>
            </CardContent>
          </Card>

          {/* Editable fields */}
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Número de WhatsApp
              </label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={editWhatsapp}
                  onChange={(e) => setEditWhatsapp(e.target.value)}
                  placeholder="+1 234 567 8900"
                  className="pl-9"
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => setStep(2)}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Volver
            </Button>
            <Button
              onClick={() => publishMutation.mutate()}
              disabled={publishMutation.isPending}
            >
              {publishMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Check className="mr-2 h-4 w-4" />
              )}
              Publicar campaña
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
