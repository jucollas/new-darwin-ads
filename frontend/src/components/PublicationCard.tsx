import { DollarSign } from "lucide-react"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { StatusBadge } from "@/components/StatusBadge"
import type { Publication } from "@/types"

interface PublicationCardProps {
  publication: Publication
  onClick: () => void
}

export function PublicationCard({ publication, onClick }: PublicationCardProps) {
  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-md overflow-hidden"
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base line-clamp-1">
            Publicación
          </CardTitle>
          <StatusBadge status={publication.status} />
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <DollarSign className="h-3 w-3" />
            ${(publication.budget_daily_cents / 100).toFixed(2)}/día
          </span>
        </div>
      </CardHeader>

      <CardContent>
        <div className="text-sm text-muted-foreground">
          {publication.published_at && (
            <span>
              Publicada:{" "}
              {new Date(publication.published_at).toLocaleDateString("es-ES", {
                day: "numeric",
                month: "short",
              })}
            </span>
          )}
          {publication.error_message && (
            <p className="text-destructive text-xs mt-1 line-clamp-1">
              {publication.error_message}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
