import { useForm, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation } from "@tanstack/react-query"
import { Loader2, X } from "lucide-react"
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
import type { Proposal, LocationEntry, LocationCountry, LocationCity } from "@/types"

// Predefined Colombian city options
const LOCATION_PRESETS: { label: string; value: LocationEntry }[] = [
  { label: "Todo Colombia", value: { type: "country", country_code: "CO" } },
  { label: "Bogotá D.C.", value: { type: "city", name: "Bogotá", region: "Bogotá D.C.", country_code: "CO" } },
  { label: "Cali, Valle del Cauca", value: { type: "city", name: "Cali", region: "Valle del Cauca", country_code: "CO" } },
  { label: "Medellín, Antioquia", value: { type: "city", name: "Medellín", region: "Antioquia", country_code: "CO" } },
  { label: "Barranquilla, Atlántico", value: { type: "city", name: "Barranquilla", region: "Atlántico", country_code: "CO" } },
  { label: "Cartagena, Bolívar", value: { type: "city", name: "Cartagena", region: "Bolívar", country_code: "CO" } },
  { label: "Bucaramanga, Santander", value: { type: "city", name: "Bucaramanga", region: "Santander", country_code: "CO" } },
  { label: "Pereira, Risaralda", value: { type: "city", name: "Pereira", region: "Risaralda", country_code: "CO" } },
  { label: "Santa Marta, Magdalena", value: { type: "city", name: "Santa Marta", region: "Magdalena", country_code: "CO" } },
  { label: "Manizales, Caldas", value: { type: "city", name: "Manizales", region: "Caldas", country_code: "CO" } },
  { label: "Ibagué, Tolima", value: { type: "city", name: "Ibagué", region: "Tolima", country_code: "CO" } },
  { label: "Villavicencio, Meta", value: { type: "city", name: "Villavicencio", region: "Meta", country_code: "CO" } },
  { label: "Cúcuta, Norte de Santander", value: { type: "city", name: "Cúcuta", region: "Norte de Santander", country_code: "CO" } },
]

/** Convert a LocationEntry to a display label */
function locationToLabel(loc: LocationEntry): string {
  if (typeof loc === "string") return loc
  if (loc.type === "city") return loc.region ? `${loc.name}, ${loc.region}` : loc.name
  if (loc.type === "country") return loc.country_code === "CO" ? "Todo Colombia" : loc.country_code
  return JSON.stringify(loc)
}

/** Convert current locations array to serializable strings for the form */
function locationsToFormKeys(locations: LocationEntry[]): string[] {
  return locations.map((loc) => {
    if (typeof loc === "string") return `country:${loc}`
    if (loc.type === "city") return `city:${loc.name}:${loc.region || ""}:${loc.country_code}`
    if (loc.type === "country") return `country:${loc.country_code}`
    return JSON.stringify(loc)
  })
}

/** Convert form key back to a LocationEntry */
function formKeyToLocation(key: string): LocationCountry | LocationCity {
  if (key.startsWith("city:")) {
    const [, name, region, country_code] = key.split(":")
    return { type: "city", name, region: region || null, country_code }
  }
  if (key.startsWith("country:")) {
    const code = key.slice("country:".length)
    return { type: "country", country_code: code }
  }
  // Legacy bare country code
  return { type: "country", country_code: key }
}

/** Get the form key for a preset */
function presetToFormKey(preset: LocationEntry): string {
  return locationsToFormKeys([preset])[0]
}

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
    locationKeys: z.array(z.string()).min(1, "Agrega al menos una ubicación"),
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
      locationKeys: locationsToFormKeys(proposal.target_audience.locations),
      cta_type: proposal.cta_type,
      whatsapp_number: proposal.whatsapp_number ?? "",
    },
  })

  const ctaType = watch("cta_type")

  const saveMutation = useMutation({
    mutationFn: async (values: ProposalFormValues) => {
      const locations = values.locationKeys.map(formKeyToLocation)
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
            locations,
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
        <Label>Ubicación del anuncio</Label>
        <Controller
          control={control}
          name="locationKeys"
          render={({ field }) => (
            <div className="space-y-2">
              {/* Selected locations */}
              {field.value.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {field.value.map((key) => (
                    <span
                      key={key}
                      className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-medium"
                    >
                      {locationToLabel(formKeyToLocation(key))}
                      <button
                        type="button"
                        onClick={() =>
                          field.onChange(field.value.filter((k) => k !== key))
                        }
                        disabled={isSaving}
                        className="ml-0.5 hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              {/* Selector */}
              <Select
                disabled={isSaving}
                onValueChange={(val) => {
                  if (val && !field.value.includes(val)) {
                    // If selecting a country, clear existing cities (no mixing)
                    const loc = formKeyToLocation(val)
                    if (loc.type === "country") {
                      field.onChange([val])
                    } else {
                      // If adding a city, remove any country entries
                      const filtered = field.value.filter(
                        (k) => !k.startsWith("country:"),
                      )
                      field.onChange([...filtered, val])
                    }
                  }
                }}
                value=""
              >
                <SelectTrigger>
                  <SelectValue placeholder="Agregar ubicación..." />
                </SelectTrigger>
                <SelectContent>
                  {LOCATION_PRESETS.map((preset) => {
                    const key = presetToFormKey(preset.value)
                    return (
                      <SelectItem
                        key={key}
                        value={key}
                        disabled={field.value.includes(key)}
                      >
                        {preset.label}
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
            </div>
          )}
        />
        {errors.locationKeys && (
          <p className="text-xs text-destructive">
            {errors.locationKeys.message}
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
