import { useRef } from "react"
import { ImagePlus, RefreshCw, Loader2, Upload } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

interface ImagePreviewProps {
  imageUrl?: string
  isGenerating?: boolean
  onRegenerate?: () => void
  onUpload?: (file: File) => void
}

export function ImagePreview({
  imageUrl,
  isGenerating = false,
  onRegenerate,
  onUpload,
}: ImagePreviewProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && onUpload) {
      onUpload(file)
    }
  }

  if (isGenerating) {
    return (
      <div className="relative aspect-square w-full rounded-lg overflow-hidden">
        <Skeleton className="h-full w-full" />
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Generando imagen con IA...
          </p>
        </div>
      </div>
    )
  }

  if (imageUrl) {
    return (
      <div className="group relative aspect-square w-full rounded-lg overflow-hidden">
        <img
          src={imageUrl}
          alt="Vista previa"
          className="h-full w-full object-cover"
        />
        <div className="absolute inset-0 flex items-center justify-center gap-2 bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
          {onRegenerate && (
            <Button variant="secondary" size="sm" onClick={onRegenerate}>
              <RefreshCw className="h-4 w-4 mr-1" />
              Regenerar imagen
            </Button>
          )}
          {onUpload && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-4 w-4 mr-1" />
              Subir
            </Button>
          )}
        </div>
        {onUpload && (
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
          />
        )}
      </div>
    )
  }

  return (
    <div className="flex aspect-square w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-muted-foreground/25">
      <ImagePlus className="h-10 w-10 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Sin imagen</p>
      {onUpload && (
        <>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-4 w-4 mr-1" />
            Subir imagen
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileChange}
          />
        </>
      )}
    </div>
  )
}
