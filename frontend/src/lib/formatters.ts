import type { KilledCampaign, LocationEntry, OptimizationRun } from "@/types"

// ---- Money (USD) ----

const usdFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
})

export function formatUSD(cents: number | null | undefined): string {
  if (!cents) return "$0.00"
  return usdFormatter.format(cents / 100)
}

// ---- Percentages ----

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null) return "—"
  // Backend stores ratios (e.g. 0.012 = 1.2%), always multiply by 100
  const pct = value * 100
  return `${pct.toLocaleString("es-CO", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}%`
}

// ---- ROAS ----

export function formatROAS(value: number | null | undefined): { text: string; color: string } {
  if (!value) return { text: "—", color: "text-muted-foreground" }
  const text = `${value.toLocaleString("es-CO", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}×`
  if (value >= 3.0) return { text, color: "text-emerald-600" }
  if (value >= 1.0) return { text, color: "text-yellow-600" }
  return { text, color: "text-red-600" }
}

// ---- Fitness Scores ----

export function formatFitnessScore(score: number): {
  label: string
  color: string
  bgColor: string
} {
  if (score >= 0.8) return { label: "Excelente", color: "text-emerald-600", bgColor: "bg-emerald-100" }
  if (score >= 0.6) return { label: "Buen rendimiento", color: "text-green-600", bgColor: "bg-green-100" }
  if (score >= 0.3) return { label: "Rendimiento medio", color: "text-yellow-600", bgColor: "bg-yellow-100" }
  return { label: "Bajo rendimiento", color: "text-red-600", bgColor: "bg-red-100" }
}

// ---- Kill Tiers ----

export function formatKillTier(tier: number): {
  label: string
  description: string
  iconName: string
  color: string
} {
  switch (tier) {
    case 1:
      return { label: "Emergencia", description: "Gasto excesivo sin resultados", iconName: "AlertTriangle", color: "text-red-600" }
    case 2:
      return { label: "Creatividad inefectiva", description: "El anuncio no generó clics suficientes", iconName: "ImageOff", color: "text-orange-600" }
    case 3:
      return { label: "Bajo rendimiento sostenido", description: "Conversaciones demasiado caras por varios días", iconName: "TrendingDown", color: "text-yellow-600" }
    case 4:
      return { label: "Ajuste gradual", description: "Rendimiento decayendo — se reduce presupuesto", iconName: "ArrowDownRight", color: "text-blue-600" }
    default:
      return { label: "Desconocido", description: "", iconName: "HelpCircle", color: "text-gray-500" }
  }
}

// ---- Kill Actions ----

export function formatKillAction(action: string): string {
  switch (action) {
    case "pause":
      return "Pausada automáticamente"
    case "reduce_budget_20":
      return "Presupuesto reducido 20%"
    case "reduce_budget_30":
      return "Presupuesto reducido 30%"
    default:
      return action
  }
}

// ---- Mutation Fields ----

export function formatMutationField(field: string): {
  label: string
  description: string
  iconName: string
} {
  switch (field) {
    case "target_audience":
      return { label: "Audiencia", description: "Se probará con un público diferente", iconName: "Users" }
    case "image_prompt":
      return { label: "Imagen", description: "Se creó una nueva imagen para el anuncio", iconName: "Image" }
    case "copy_text":
      return { label: "Texto del anuncio", description: "Se escribió un nuevo copy publicitario", iconName: "Type" }
    case "welcome_message":
      return { label: "Mensaje de bienvenida", description: "Se cambió el saludo inicial en WhatsApp", iconName: "MessageSquare" }
    default:
      return { label: field, description: "", iconName: "HelpCircle" }
  }
}

// ---- Campaign Classification ----

export function formatClassification(c: string): {
  label: string
  description: string
  iconName: string
  color: string
} {
  switch (c) {
    case "immature":
      return { label: "Recopilando datos", description: "Muy reciente para evaluar", iconName: "Clock", color: "text-gray-500" }
    case "early_stage":
      return { label: "Evaluación temprana", description: "Analizando señales iniciales", iconName: "BarChart2", color: "text-blue-500" }
    case "mature":
      return { label: "Evaluación completa", description: "Datos suficientes para decidir", iconName: "CheckCircle", color: "text-green-500" }
    default:
      return { label: c, description: "", iconName: "HelpCircle", color: "text-gray-500" }
  }
}

// ---- Money Saved Calculator ----

function savedFraction(action: string): number {
  switch (action) {
    case "pause": return 1.0
    case "reduce_budget_30": return 0.30
    case "reduce_budget_20": return 0.20
    default: return 1.0
  }
}

export function calculateMoneySaved(killedCampaigns: KilledCampaign[]): number {
  return killedCampaigns.reduce((sum, k) => {
    const daily = k.budget_daily_cents ?? 0
    return daily > 0 ? sum + daily * savedFraction(k.action) * 7 : sum
  }, 0)
}

export function calculateMoneySavedFromRuns(runs: OptimizationRun[]): number {
  const seen = new Set<string>()
  let total = 0
  for (const run of runs) {
    for (const k of run.campaigns_killed ?? []) {
      if (!seen.has(k.campaign_id)) {
        seen.add(k.campaign_id)
        const daily = k.budget_daily_cents ?? 0
        if (daily > 0) total += daily * savedFraction(k.action) * 7
      }
    }
  }
  return total
}

// ---- Portfolio Averages from Optimization Runs ----

export function calculatePortfolioROASOverTime(
  runs: OptimizationRun[]
): Array<{ date: string; avgRoas: number; avgCostPerConv: number }> {
  const results: Array<{ date: string; avgRoas: number; avgCostPerConv: number }> = []

  const sorted = [...runs].sort(
    (a, b) => new Date(a.ran_at).getTime() - new Date(b.ran_at).getTime()
  )

  for (const run of sorted) {
    const scores = Object.values(run.fitness_scores ?? {})
    const mature = scores.filter((s) => s.classification === "mature")
    if (mature.length === 0) continue

    let roasSum = 0
    let roasCount = 0
    let cpcSum = 0
    let cpcCount = 0

    for (const s of mature) {
      const roas = s.raw_scores?.roas
      if (roas != null) {
        roasSum += roas
        roasCount++
      }
      const cpc = s.raw_scores?.cost_per_conversion
      if (cpc != null) {
        cpcSum += cpc / 100
        cpcCount++
      }
    }

    if (roasCount > 0) {
      results.push({
        date: run.ran_at,
        avgRoas: roasSum / roasCount,
        avgCostPerConv: cpcCount > 0 ? cpcSum / cpcCount : 0,
      })
    }
  }

  return results
}

// ---- Location Formatting ----

const COUNTRY_NAMES: Record<string, string> = {
  CO: "Colombia",
  MX: "México",
  AR: "Argentina",
  PE: "Perú",
  CL: "Chile",
  EC: "Ecuador",
}

export function formatLocation(loc: LocationEntry): string {
  if (typeof loc === "string") return COUNTRY_NAMES[loc] || loc
  if (loc.type === "city") {
    return loc.region ? `${loc.name}, ${loc.region}` : loc.name
  }
  if (loc.type === "country") {
    return COUNTRY_NAMES[loc.country_code] || loc.country_code
  }
  return JSON.stringify(loc)
}

export function formatLocations(locations: LocationEntry[] | undefined | null): string {
  if (!locations || !Array.isArray(locations) || locations.length === 0) return "Sin ubicación"
  return locations.map(formatLocation).join(" · ")
}

export function formatGeoLocations(geo: Record<string, unknown> | null | undefined): string {
  if (!geo) return "Colombia (todo el país)"

  if (geo.cities && Array.isArray(geo.cities)) {
    return (geo.cities as Array<Record<string, string>>)
      .map((c) => {
        const name = c.name || "Ciudad desconocida"
        const region = c.region ? `, ${c.region}` : ""
        return `${name}${region}`
      })
      .join(" · ")
  }

  if (geo.countries && Array.isArray(geo.countries)) {
    return (geo.countries as string[])
      .map((c) => COUNTRY_NAMES[c] || c)
      .join(" · ")
  }

  return "Ubicación no especificada"
}

// ---- Time Formatting ----

export function formatTimeAgo(isoDate: string): string {
  const now = Date.now()
  const then = new Date(isoDate).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMs / 3600000)
  const diffDay = Math.floor(diffMs / 86400000)
  const diffWeek = Math.floor(diffDay / 7)

  if (diffMin < 1) return "Hace un momento"
  if (diffMin < 60) return `Hace ${diffMin} minuto${diffMin === 1 ? "" : "s"}`
  if (diffHr < 24) return `Hace ${diffHr} hora${diffHr === 1 ? "" : "s"}`
  if (diffDay < 14) return `Hace ${diffDay} día${diffDay === 1 ? "" : "s"}`
  return `Hace ${diffWeek} semana${diffWeek === 1 ? "" : "s"}`
}

const MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

export function formatDate(isoDate: string): string {
  const d = new Date(isoDate)
  return `${d.getDate()} ${MONTHS_ES[d.getMonth()]} ${d.getFullYear()}`
}

export function formatShortDate(isoDate: string): string {
  const d = new Date(isoDate)
  return `${d.getDate()} ${MONTHS_ES[d.getMonth()]}`
}
