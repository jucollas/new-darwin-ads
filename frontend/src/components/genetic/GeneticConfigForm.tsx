import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { GeneticConfig, GeneticConfigUpdate } from "@/types"
import { cn } from "@/lib/utils"

const configSchema = z.object({
  target_cpa_cents: z.coerce.number().min(50).max(100000),
  max_active_campaigns: z.coerce.number().min(5).max(20),
  duplicate_min_roas: z.coerce.number().min(1.0).max(20.0),
  min_days_active: z.coerce.number().min(2).max(7),
  // Advanced
  min_impressions_to_evaluate: z.coerce.number().min(0).optional(),
  emergency_kill_cpa_multiplier: z.coerce.number().min(1).optional(),
  graduated_cpa_threshold: z.coerce.number().min(1).optional(),
  max_budget_increase_pct: z.coerce.number().min(0).max(100).optional(),
  budget_increase_interval_days: z.coerce.number().min(1).optional(),
})

type FormValues = z.infer<typeof configSchema>

interface GeneticConfigFormProps {
  config: GeneticConfig
  onSave: (data: GeneticConfigUpdate) => void
  isSaving: boolean
}

export default function GeneticConfigForm({
  config,
  onSave,
  isSaving,
}: GeneticConfigFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(configSchema),
    defaultValues: {
      target_cpa_cents: Math.round(config.target_cpa_cents / 100),
      max_active_campaigns: config.max_active_campaigns,
      duplicate_min_roas: config.duplicate_min_roas,
      min_days_active: config.min_days_active,
      min_impressions_to_evaluate: config.min_impressions_to_evaluate,
      emergency_kill_cpa_multiplier: config.emergency_kill_cpa_multiplier,
      graduated_cpa_threshold: config.graduated_cpa_threshold,
      max_budget_increase_pct: config.max_budget_increase_pct,
      budget_increase_interval_days: config.budget_increase_interval_days,
    },
  })

  const maxCampaigns = watch("max_active_campaigns")
  const minDays = watch("min_days_active")

  const onSubmit = (values: FormValues) => {
    const update: GeneticConfigUpdate = {
      target_cpa_cents: Math.round(values.target_cpa_cents * 100),
      max_active_campaigns: values.max_active_campaigns,
      duplicate_min_roas: values.duplicate_min_roas,
      min_days_active: values.min_days_active,
    }
    if (values.min_impressions_to_evaluate != null)
      update.min_impressions_to_evaluate = values.min_impressions_to_evaluate
    if (values.emergency_kill_cpa_multiplier != null)
      update.emergency_kill_cpa_multiplier = values.emergency_kill_cpa_multiplier
    if (values.graduated_cpa_threshold != null)
      update.graduated_cpa_threshold = values.graduated_cpa_threshold
    if (values.max_budget_increase_pct != null)
      update.max_budget_increase_pct = values.max_budget_increase_pct
    if (values.budget_increase_interval_days != null)
      update.budget_increase_interval_days = values.budget_increase_interval_days
    onSave(update)
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6 max-w-2xl mx-auto">
      {/* Basic Settings */}
      <div className="space-y-2">
        <Label htmlFor="target_cpa_cents">
          Objetivo de costo por conversación (USD)
        </Label>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">$</span>
          <Input
            id="target_cpa_cents"
            type="number"
            className="max-w-xs"
            {...register("target_cpa_cents")}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          El sistema pausará campañas que cuesten mucho más que esto
        </p>
        {errors.target_cpa_cents && (
          <p className="text-sm text-red-500">{errors.target_cpa_cents.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label>Máximo de campañas activas</Label>
        <Select
          value={String(maxCampaigns)}
          onValueChange={(v) => setValue("max_active_campaigns", Number(v))}
        >
          <SelectTrigger className="max-w-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[5, 10, 15, 20].map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n} campañas
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Más campañas = más variantes probándose al mismo tiempo
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="duplicate_min_roas">ROAS mínimo para replicar</Label>
        <Input
          id="duplicate_min_roas"
          type="number"
          step="0.5"
          className="max-w-xs"
          {...register("duplicate_min_roas")}
        />
        <p className="text-xs text-muted-foreground">
          Solo campañas con un retorno mayor a este valor serán replicadas
        </p>
        {errors.duplicate_min_roas && (
          <p className="text-sm text-red-500">{errors.duplicate_min_roas.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label>Días antes de evaluar</Label>
        <Select
          value={String(minDays)}
          onValueChange={(v) => setValue("min_days_active", Number(v))}
        >
          <SelectTrigger className="max-w-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {[2, 3, 5, 7].map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n} días
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Cuánto espera el sistema antes de juzgar una campaña nueva
        </p>
      </div>

      {/* Advanced Settings */}
      <div className="border rounded-lg">
        <button
          type="button"
          className="flex w-full items-center justify-between p-4 text-left text-sm font-medium hover:bg-muted/50 transition-colors"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <span>⚙️ Configuración avanzada (usuarios expertos)</span>
          <ChevronDown
            className={cn(
              "h-4 w-4 transition-transform duration-200",
              showAdvanced && "rotate-180"
            )}
          />
        </button>

        {showAdvanced && (
          <div className="p-4 pt-0 space-y-4 border-t">
            <AdvancedField
              id="min_impressions_to_evaluate"
              label="Impresiones mínimas para evaluar"
              helper="La campaña necesita al menos esta cantidad de impresiones antes de ser evaluada"
              register={register}
              error={errors.min_impressions_to_evaluate?.message}
            />
            <AdvancedField
              id="emergency_kill_cpa_multiplier"
              label="Multiplicador de emergencia (×)"
              helper="Pausa inmediata si el costo supera el objetivo × este valor (ej: 3× = pausa si cuesta el triple del objetivo)"
              register={register}
              step="0.5"
              error={errors.emergency_kill_cpa_multiplier?.message}
            />
            <AdvancedField
              id="graduated_cpa_threshold"
              label="Umbral para reducción gradual (×)"
              helper="Empieza a reducir presupuesto cuando el costo supera el objetivo × este valor"
              register={register}
              step="0.5"
              error={errors.graduated_cpa_threshold?.message}
            />
            <AdvancedField
              id="max_budget_increase_pct"
              label="Incremento máximo de presupuesto (%)"
              helper="Cuánto puede aumentar el presupuesto de una campaña ganadora por ciclo"
              register={register}
              error={errors.max_budget_increase_pct?.message}
            />
            <AdvancedField
              id="budget_increase_interval_days"
              label="Días entre incrementos"
              helper="Cada cuántos días se puede subir el presupuesto"
              register={register}
              error={errors.budget_increase_interval_days?.message}
            />
          </div>
        )}
      </div>

      <Button type="submit" disabled={isSaving}>
        {isSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        Guardar configuración
      </Button>
    </form>
  )
}

function AdvancedField({
  id,
  label,
  helper,
  register,
  step,
  error,
}: {
  id: string
  label: string
  helper: string
  register: ReturnType<typeof useForm<FormValues>>["register"]
  step?: string
  error?: string
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-sm">
        {label}
      </Label>
      <Input
        id={id}
        type="number"
        step={step}
        className="max-w-xs"
        {...register(id as keyof FormValues)}
      />
      <p className="text-xs text-muted-foreground">{helper}</p>
      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  )
}
