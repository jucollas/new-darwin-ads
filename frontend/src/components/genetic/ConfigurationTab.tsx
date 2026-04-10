import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import GeneticConfigForm from "./GeneticConfigForm"
import HowItWorks from "./HowItWorks"
import type { GeneticConfig, GeneticConfigUpdate } from "@/types"

interface ConfigurationTabProps {
  config: GeneticConfig | undefined
  onSave: (data: GeneticConfigUpdate) => void
  isSaving: boolean
}

export default function ConfigurationTab({
  config,
  onSave,
  isSaving,
}: ConfigurationTabProps) {
  if (!config) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No se pudo cargar la configuración.
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Ajustes del optimizador</CardTitle>
        </CardHeader>
        <CardContent>
          <GeneticConfigForm
            config={config}
            onSave={onSave}
            isSaving={isSaving}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">¿Cómo funciona?</CardTitle>
        </CardHeader>
        <CardContent>
          <HowItWorks />
        </CardContent>
      </Card>
    </div>
  )
}
