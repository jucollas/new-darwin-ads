import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface MetricTooltipProps {
  label: string
  value: string
  tooltip: string
}

export function MetricTooltip({ label, value, tooltip }: MetricTooltipProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help">
            <span className="text-muted-foreground">{label}: </span>
            <span className="font-medium text-foreground">{value}</span>
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-sm">
          {tooltip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
