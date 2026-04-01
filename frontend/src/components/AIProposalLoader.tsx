import { Skeleton } from "@/components/ui/skeleton"

export function AIProposalLoader() {
  return (
    <div className="space-y-6">
      <p className="text-center text-muted-foreground animate-pulse">
        La IA esta generando tus propuestas...
      </p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="rounded-lg border bg-card p-6 shadow-sm space-y-4"
          >
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-5 w-3/4" />
            <div className="space-y-2">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-3 w-4/6" />
            </div>
            <div className="space-y-2 pt-2">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/3" />
            </div>
            <div className="pt-4 space-y-2">
              <Skeleton className="h-16 w-full rounded-md" />
            </div>
            <div className="flex gap-2 pt-2">
              <Skeleton className="h-10 flex-1" />
              <Skeleton className="h-10 w-28" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
