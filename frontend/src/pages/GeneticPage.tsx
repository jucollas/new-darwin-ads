import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Dna, Loader2, AlertCircle } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useOptimizationRuns,
  useGeneticConfig,
  useMetricsSummaryGenetic,
  useTopPerformersGenetic,
  useTriggerOptimization,
  useUpdateGeneticConfig,
} from "@/hooks/useGeneticAlgorithm"
import { useCampaignNames } from "@/hooks/useCampaignNames"
import ImpactSummaryTab from "@/components/genetic/ImpactSummaryTab"
import OptimizationHistoryTab from "@/components/genetic/OptimizationHistoryTab"
import CampaignHealthTab from "@/components/genetic/CampaignHealthTab"
import ConfigurationTab from "@/components/genetic/ConfigurationTab"

export default function GeneticPage() {
  const [activeTab, setActiveTab] = useState("impact")

  // ---- Data fetching at page level ----
  const {
    data: runs = [],
    isLoading: runsLoading,
    error: runsError,
    refetch: refetchRuns,
  } = useOptimizationRuns(1, 20)

  const {
    data: config,
    isLoading: configLoading,
    error: configError,
  } = useGeneticConfig()

  const {
    data: metrics,
    isLoading: metricsLoading,
  } = useMetricsSummaryGenetic()

  const {
    data: topPerformers = [],
    isLoading: performersLoading,
  } = useTopPerformersGenetic()

  const triggerMutation = useTriggerOptimization()
  const updateConfigMutation = useUpdateGeneticConfig()

  // ---- Extract all campaign IDs for name resolution ----
  const allCampaignIds = useMemo(() => {
    const ids = new Set<string>()
    for (const run of runs) {
      for (const [id] of Object.entries(run.fitness_scores ?? {})) {
        ids.add(id)
      }
      for (const k of run.campaigns_killed ?? []) {
        ids.add(k.campaign_id)
      }
      for (const d of run.campaigns_duplicated ?? []) {
        ids.add(d.parent_id)
        ids.add(d.new_campaign_id)
      }
    }
    // Also add top performers
    for (const p of topPerformers) {
      ids.add(p.campaign_id)
    }
    return [...ids]
  }, [runs, topPerformers])

  const { getName, isLoading: namesLoading } = useCampaignNames(allCampaignIds)

  // ---- Loading state ----
  const isLoading = runsLoading || configLoading

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-72" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-[350px]" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    )
  }

  // ---- Error state ----
  if (runsError || configError) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
          <div>
            <h3 className="font-semibold text-red-800">Error cargando datos</h3>
            <p className="text-sm text-red-700 mt-1">
              {(runsError as Error)?.message ||
                (configError as Error)?.message ||
                "Intenta de nuevo en unos minutos"}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => refetchRuns()}
            >
              Reintentar
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // ---- Empty state (no runs at all) ----
  if (runs.length === 0) {
    return (
      <div className="p-6">
        <div className="flex flex-col items-center justify-center py-20 text-center gap-4 max-w-md mx-auto">
          <Dna className="h-16 w-16 text-muted-foreground/50" />
          <h2 className="text-xl font-semibold">
            Tu optimizador automático está listo
          </h2>
          <p className="text-muted-foreground">
            El sistema evaluará tus campañas automáticamente cada 24 horas para
            maximizar tu retorno.
          </p>
          <p className="text-sm text-muted-foreground">
            Para empezar necesitas al menos 1 campaña publicada con 3+ días
            activa.
          </p>
          <Link to="/campaigns">
            <Button variant="outline">Ir a mis campañas &rarr;</Button>
          </Link>
          <div className="pt-2">
            <p className="text-sm text-muted-foreground mb-2">
              ¿Quieres ejecutar la primera optimización ahora?
            </p>
            <Button
              onClick={() => triggerMutation.mutate()}
              disabled={triggerMutation.isPending}
            >
              {triggerMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              Ejecutar primera optimización
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // ---- Main content with tabs ----
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Optimizador de Campañas</h1>
        <p className="text-muted-foreground">
          Tu sistema de inteligencia artificial trabajando 24/7 para maximizar tus resultados
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="impact">Resumen de Impacto</TabsTrigger>
          <TabsTrigger value="history">Historial</TabsTrigger>
          <TabsTrigger value="campaigns">Mis Campañas</TabsTrigger>
          <TabsTrigger value="config">Configuración</TabsTrigger>
        </TabsList>

        <TabsContent value="impact" className="mt-6">
          <ImpactSummaryTab
            runs={runs}
            config={config}
            metrics={metrics}
            topPerformers={topPerformers}
            getName={getName}
            onSwitchToHistory={() => setActiveTab("history")}
          />
        </TabsContent>

        <TabsContent value="history" className="mt-6">
          <OptimizationHistoryTab
            runs={runs}
            config={config}
            getName={getName}
            onTriggerOptimization={() => triggerMutation.mutate()}
            isOptimizing={triggerMutation.isPending}
          />
        </TabsContent>

        <TabsContent value="campaigns" className="mt-6">
          <CampaignHealthTab
            runs={runs}
            config={config}
            getName={getName}
          />
        </TabsContent>

        <TabsContent value="config" className="mt-6">
          <ConfigurationTab
            config={config}
            onSave={(data) => updateConfigMutation.mutate(data)}
            isSaving={updateConfigMutation.isPending}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
