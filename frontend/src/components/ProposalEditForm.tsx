import { useForm, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { queryClient } from "@/lib/queryClient"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { TagInput } from "@/components/TagInput"
import type { Proposal } from "@/types"

const proposalSchema = z
  .object({
    copy_text: z.string().min(1, "El copy es obligatorio"),
    script: z.string().min(1, "El script es obligatorio"),
    image_prompt: z.string().min(1, "El prompt de imagen es obligatorio"),
    age_min: z.coerce
      .number()
      .min(18, "Mínimo 18")
      .max(65, "Máximo 65"),
    age_max: z.coerce
      .number()
      .min(18, "Mínimo 18")
      .max(65, "Máximo 65"),
    genders: z.array(z.string()).min(1, "Selecciona al menos un género"),
    interests: z.array(z.string()).min(1, "Agrega al menos un interés"),
    locations: z.array(z.string()).min(1, "Agrega al menos una ubicación"),
    cta_type: z.enum(["whatsapp_chat", "link", "call"]),
    whatsapp_number: z.string().optional(),
  })
  .refine((data) => data.age_max >= data.age_min, {
    message: "La edad máxima debe ser mayor o igual a la mínima",
    path: ["age_max"],
  })
  .refine(
    (data) => {
      if (data.cta_type === "whatsapp_chat") {
        return !!data.whatsapp_number && data.whatsapp_number.trim().length > 0
      }
      return true
    },
    {
      message: "El número de WhatsApp es obligatorio para este CTA",
      path: ["whatsapp_number"],
    },
  )
  .refine(
    (data) => {
      if (
        data.cta_type === "whatsapp_chat" &&
        data.whatsapp_number
      ) {
        return /^\+\d{7,15}$/.test(data.whatsapp_number)
      }
      return true
    },
    {
      message: "Formato inválido. Usa +[código país][número] (ej: +573001234567)",
      path: ["whatsapp_number"],
    },
  )

type ProposalFormValues = z.infer<typeof proposalSchema>

interface ProposalEditFormProps {
  proposal: Proposal
  onSaved: (updated: Proposal) => void
  onCancel: () => void
}

const GENDER_OPTIONS = [
  { value: "male", label: "Masculino" },
  { value: "female", label: "Femenino" },
  { value: "all", label: "Todos" },
]

export function ProposalEditForm({
  proposal,
  onSaved,
  onCancel,
}: ProposalEditFormProps) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<ProposalFormValues>({
    resolver: zodResolver(proposalSchema),
    defaultValues: {
      copy_text: proposal.copy_text,
      script: proposal.script,
      image_prompt: proposal.image_prompt,
      age_min: proposal.target_audience.age_min,
      age_max: proposal.target_audience.age_max,
      genders: proposal.target_audience.genders,
      interests: proposal.target_audience.interests,
      locations: proposal.target_audience.locations,
      cta_type: proposal.cta_type,
      whatsapp_number: proposal.whatsapp_number ?? "",
    },
  })

  const ctaType = watch("cta_type")

  const saveMutation = useMutation({
    mutationFn: async (values: ProposalFormValues) => {
      const { data } = await api.put(
        ENDPOINTS.campaigns.updateProposal(proposal.campaign_id, proposal.id),
        {
          copy_text: values.copy_text,
          script: values.script,
          image_prompt: values.image_prompt,
          target_audience: {
            age_min: values.age_min,
            age_max: values.age_max,
            genders: values.genders,
            interests: values.interests,
            locations: values.locations,
          },
          cta_type: values.cta_type,
          whatsapp_number:
            values.cta_type === "whatsapp_chat"
              ? values.whatsapp_number
              : null,
        },
      )
      return data as Proposal
    },
    onSuccess: (updated) => {
      toast.success("Propuesta guardada")
      queryClient.invalidateQueries({
        queryKey: ["campaign-proposals", proposal.campaign_id],
      })
      onSaved(updated)
    },
    onError: () => {
      toast.error("Error al guardar la propuesta")
    },
  })

  const onSubmit = (values: ProposalFormValues) => {
    saveMutation.mutate(values)
  }

  const isSaving = saveMutation.isPending

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {/* Copy text */}
      <div className="space-y-1.5">
        <Label htmlFor="copy_text">Copy</Label>
        <Textarea
          id="copy_text"
          rows={3}
          disabled={isSaving}
          {...register("copy_text")}
        />
        {errors.copy_text && (
          <p className="text-xs text-destructive">{errors.copy_text.message}</p>
        )}
      </div>

      {/* Script */}
      <div className="space-y-1.5">
        <Label htmlFor="script">Script</Label>
        <Textarea
          id="script"
          rows={3}
          disabled={isSaving}
          {...register("script")}
        />
        {errors.script && (
          <p className="text-xs text-destructive">{errors.script.message}</p>
        )}
      </div>

      {/* Image prompt */}
      <div className="space-y-1.5">
        <Label htmlFor="image_prompt">Prompt de imagen</Label>
        <Textarea
          id="image_prompt"
          rows={2}
          disabled={isSaving}
          {...register("image_prompt")}
        />
        {errors.image_prompt && (
          <p className="text-xs text-destructive">
            {errors.image_prompt.message}
          </p>
        )}
      </div>

      {/* Age range */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="age_min">Edad mínima</Label>
          <Input
            id="age_min"
            type="number"
            min={18}
            max={65}
            disabled={isSaving}
            {...register("age_min")}
          />
          {errors.age_min && (
            <p className="text-xs text-destructive">
              {errors.age_min.message}
            </p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="age_max">Edad máxima</Label>
          <Input
            id="age_max"
            type="number"
            min={18}
            max={65}
            disabled={isSaving}
            {...register("age_max")}
          />
          {errors.age_max && (
            <p className="text-xs text-destructive">
              {errors.age_max.message}
            </p>
          )}
        </div>
      </div>

      {/* Genders */}
      <div className="space-y-1.5">
        <Label>Géneros</Label>
        <Controller
          control={control}
          name="genders"
          render={({ field }) => (
            <div className="flex flex-wrap gap-3">
              {GENDER_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className="flex items-center gap-1.5 text-sm"
                >
                  <input
                    type="checkbox"
                    disabled={isSaving}
                    checked={field.value.includes(opt.value)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        field.onChange([...field.value, opt.value])
                      } else {
                        field.onChange(
                          field.value.filter((v) => v !== opt.value),
                        )
                      }
                    }}
                    className="rounded border-input"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          )}
        />
        {errors.genders && (
          <p className="text-xs text-destructive">{errors.genders.message}</p>
        )}
      </div>

      {/* Interests */}
      <div className="space-y-1.5">
        <Label>Intereses</Label>
        <Controller
          control={control}
          name="interests"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="Agrega un interés y presiona Enter"
              disabled={isSaving}
            />
          )}
        />
        {errors.interests && (
          <p className="text-xs text-destructive">
            {errors.interests.message}
          </p>
        )}
      </div>

      {/* Locations */}
      <div className="space-y-1.5">
        <Label>Ubicaciones (código ISO)</Label>
        <Controller
          control={control}
          name="locations"
          render={({ field }) => (
            <TagInput
              value={field.value}
              onChange={field.onChange}
              placeholder="Agrega un código ISO (ej: CO, MX)"
              disabled={isSaving}
            />
          )}
        />
        {errors.locations && (
          <p className="text-xs text-destructive">
            {errors.locations.message}
          </p>
        )}
      </div>

      {/* CTA type */}
      <div className="space-y-1.5">
        <Label>Tipo de CTA</Label>
        <Controller
          control={control}
          name="cta_type"
          render={({ field }) => (
            <Select
              value={field.value}
              onValueChange={field.onChange}
              disabled={isSaving}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="whatsapp_chat">WhatsApp Chat</SelectItem>
                <SelectItem value="link">Link</SelectItem>
                <SelectItem value="call">Llamada</SelectItem>
              </SelectContent>
            </Select>
          )}
        />
      </div>

      {/* WhatsApp number */}
      {ctaType === "whatsapp_chat" && (
        <div className="space-y-1.5">
          <Label htmlFor="whatsapp_number">Número de WhatsApp</Label>
          <Input
            id="whatsapp_number"
            placeholder="+573001234567"
            disabled={isSaving}
            {...register("whatsapp_number")}
          />
          {errors.whatsapp_number && (
            <p className="text-xs text-destructive">
              {errors.whatsapp_number.message}
            </p>
          )}
        </div>
      )}

      {/* API error */}
      {saveMutation.isError && (
        <p className="text-sm text-destructive">
          Error al guardar. Intenta de nuevo.
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <Button type="submit" disabled={isSaving}>
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Guardar
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isSaving}
        >
          Cancelar
        </Button>
      </div>
    </form>
  )
}
