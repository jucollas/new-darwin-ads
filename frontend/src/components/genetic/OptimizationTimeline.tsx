import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/formatters"
import type { OptimizationRun, GeneticConfig } from "@/types"
import RunDetail from "./RunDetail"

interface OptimizationTimelineProps {
  runs: OptimizationRun[]
  config: GeneticConfig | undefined
  getName: (id: string) => string
}

export default function OptimizationTimeline({
  runs,
  config,
  getName,
}: OptimizationTimelineProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (!runs.length) return null

  return (
    <div className="relative space-y-0">
      {runs.map((run, i) => {
        const killed = (run.campaigns_killed ?? []).length
        const duped = (run.campaigns_duplicated ?? []).length
        const isExpanded = expandedId === run.id
        const isLast = i === runs.length - 1

        // Dot color logic
        let dotColor = "bg-yellow-500"
        if (duped > killed) dotColor = "bg-emerald-500"
        else if (killed > duped) dotColor = "bg-red-500"

        return (
          <div key={run.id} className="relative pl-8">
            {/* Vertical line */}
            {!isLast && (
              <div className="absolute left-[11px] top-6 bottom-0 w-0.5 bg-border" />
            )}

            {/* Dot */}
            <div
              className={cn(
                "absolute left-1 top-2 h-5 w-5 rounded-full border-2 border-background",
                dotColor
              )}
            />

            {/* Content */}
            <div className="pb-6">
              <button
                type="button"
                className="flex items-center gap-2 text-left w-full group"
                onClick={() =>
                  setExpandedId(isExpanded ? null : run.id)
                }
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">
                    Generación #{run.generation_number}{" "}
                    <span className="text-muted-foreground font-normal">
                      — {formatDate(run.ran_at)}
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {run.campaigns_evaluated} evaluadas &middot; {killed}{" "}
                    pausadas &middot; {duped} variantes
                  </p>
                </div>
                <span className="text-muted-foreground group-hover:text-foreground transition-colors">
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </span>
              </button>

              {isExpanded && (
                <div className="mt-3 border-l-2 border-muted pl-4">
                  <RunDetail
                    run={run}
                    config={config}
                    getName={getName}
                  />
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
