import { ChevronDown } from "lucide-react"
import { useState } from "react"
import { cn } from "@/lib/utils"

const FAQ_ITEMS = [
  {
    question: "¿Qué hace el optimizador automático?",
    answer:
      "Cada 24 horas, el sistema analiza todas tus campañas activas en Meta Ads. Pausa las que están desperdiciando dinero y crea nuevas versiones de las que mejor funcionan, probando con audiencias, imágenes o textos diferentes.",
  },
  {
    question: "¿Cómo decide cuáles pausar?",
    answer:
      "El sistema evalúa cada campaña según cuatro criterios: retorno sobre inversión (ROAS), costo por conversación en WhatsApp, tasa de clics (CTR) y costo por clic (CPC). Las campañas que cuestan mucho más que tu objetivo se pausan automáticamente para proteger tu presupuesto.",
  },
  {
    question: '¿Qué significa "crear una variante"?',
    answer:
      "Cuando una campaña tiene buenos resultados, el sistema usa inteligencia artificial para crear una versión similar con un cambio: puede ser una audiencia diferente, una nueva imagen, o un texto modificado. Así encuentra combinaciones aún mejores.",
  },
  {
    question: "¿Puedo reactivar una campaña pausada?",
    answer:
      'Sí. Ve a la campaña en la sección "Mis Campañas" y usa el botón de reactivar. Ten en cuenta que el optimizador la volverá a pausar si no mejora su rendimiento.',
  },
  {
    question: "¿Cuánto tarda en mostrar resultados?",
    answer:
      "Las primeras evaluaciones ocurren después de 3 días. Resultados significativos suelen verse después de 2-3 semanas (5-7 generaciones), cuando el sistema ha probado suficientes variantes para encontrar las ganadoras.",
  },
]

export default function HowItWorks() {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold mb-4">Preguntas frecuentes</h3>
      {FAQ_ITEMS.map((item, i) => (
        <div key={i} className="border rounded-lg">
          <button
            type="button"
            className="flex w-full items-center justify-between p-4 text-left font-medium hover:bg-muted/50 transition-colors"
            onClick={() => setOpenIndex(openIndex === i ? null : i)}
          >
            {item.question}
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 transition-transform duration-200",
                openIndex === i && "rotate-180"
              )}
            />
          </button>
          {openIndex === i && (
            <div className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed">
              {item.answer}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
