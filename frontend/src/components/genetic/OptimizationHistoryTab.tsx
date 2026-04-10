import { Loader2, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import OptimizationTimeline from "./OptimizationTimeline"
import type { OptimizationRun, GeneticConfig } from "@/types"

interface OptimizationHistoryTabProps {
  runs: OptimizationRun[]
  config: GeneticConfig | undefined
  getName: (id: string) => string
  onTriggerOptimization: () => void
  isOptimizing: boolean
}

export default function OptimizationHistoryTab({
  runs,
  config,
  getName,
  onTriggerOptimization,
  isOptimizing,
}: OptimizationHistoryTabProps) {
  return (
    <div className="space-y-6">
      {/* Run Now */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <Button
          onClick={onTriggerOptimization}
          disabled={isOptimizing}
        >
          {isOptimizing ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          {isOptimizing ? "Optimizando..." : "Ejecutar optimización ahora"}
        </Button>
        <p className="text-xs text-muted-foreground">
          La optimización automática se ejecuta cada 24 horas a las 3:00 AM
        </p>
      </div>

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Historial de optimizaciones
          </CardTitle>
        </CardHeader>
        <CardContent>
          {runs.length > 0 ? (
            <OptimizationTimeline
              runs={runs}
              config={config}
              getName={getName}
            />
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No hay optimizaciones registradas aún.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
