import { cn } from "@/lib/utils"
import { Image as ImageIcon, MessageCircle, ThumbsUp, Share2, Heart, Send, Bookmark } from "lucide-react"
import { Button } from "@/components/ui/button"

interface AdPreviewProps {
  platform: "facebook" | "instagram" | "tiktok"
  copy: string
  imageUrl?: string
  cta?: string
  userName?: string
}

function FacebookPreview({ copy, imageUrl, cta, userName }: Omit<AdPreviewProps, "platform">) {
  return (
    <div className="max-w-sm rounded-lg border bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-2 p-3">
        <div className="h-10 w-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-sm">
          {(userName ?? "A").charAt(0).toUpperCase()}
        </div>
        <div>
          <p className="text-sm font-semibold">{userName ?? "Tu Negocio"}</p>
          <p className="text-xs text-gray-500">Publicidad</p>
        </div>
      </div>

      {/* Copy */}
      <div className="px-3 pb-2">
        <p className="text-sm whitespace-pre-line">{copy}</p>
      </div>

      {/* Image */}
      <div className="aspect-video bg-gray-100 relative">
        {imageUrl ? (
          <img src={imageUrl} alt="Ad preview" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageIcon className="h-12 w-12 text-gray-300" />
          </div>
        )}
      </div>

      {/* CTA */}
      <div className="p-3 border-t">
        <Button className="w-full bg-green-600 hover:bg-green-700 text-white">
          <MessageCircle className="h-4 w-4 mr-2" />
          {cta ?? "Enviar mensaje por WhatsApp"}
        </Button>
      </div>

      {/* Reactions */}
      <div className="flex items-center justify-around border-t p-2 text-gray-500 text-xs">
        <button className="flex items-center gap-1 hover:text-blue-600">
          <ThumbsUp className="h-4 w-4" /> Me gusta
        </button>
        <button className="flex items-center gap-1 hover:text-blue-600">
          <MessageCircle className="h-4 w-4" /> Comentar
        </button>
        <button className="flex items-center gap-1 hover:text-blue-600">
          <Share2 className="h-4 w-4" /> Compartir
        </button>
      </div>
    </div>
  )
}

function InstagramPreview({ copy, imageUrl, cta, userName }: Omit<AdPreviewProps, "platform">) {
  return (
    <div className="max-w-sm rounded-lg border bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-2 p-3">
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-orange-400 flex items-center justify-center text-white font-bold text-xs">
          {(userName ?? "A").charAt(0).toUpperCase()}
        </div>
        <div>
          <p className="text-sm font-semibold">{userName ?? "tu_negocio"}</p>
          <p className="text-xs text-gray-500">Publicidad</p>
        </div>
      </div>

      {/* Image (square) */}
      <div className="aspect-square bg-gray-100 relative">
        {imageUrl ? (
          <img src={imageUrl} alt="Ad preview" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageIcon className="h-12 w-12 text-gray-300" />
          </div>
        )}
      </div>

      {/* CTA */}
      <div className="px-3 pt-2">
        <Button className="w-full bg-green-600 hover:bg-green-700 text-white">
          <MessageCircle className="h-4 w-4 mr-2" />
          {cta ?? "Enviar mensaje por WhatsApp"}
        </Button>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3">
          <Heart className="h-5 w-5" />
          <MessageCircle className="h-5 w-5" />
          <Send className="h-5 w-5" />
        </div>
        <Bookmark className="h-5 w-5" />
      </div>

      {/* Copy */}
      <div className="px-3 pb-3">
        <p className="text-sm">
          <span className="font-semibold mr-1">{userName ?? "tu_negocio"}</span>
          <span className="whitespace-pre-line">{copy}</span>
        </p>
      </div>
    </div>
  )
}

function TikTokPreview({ copy, imageUrl, cta, userName }: Omit<AdPreviewProps, "platform">) {
  return (
    <div className="max-w-sm rounded-lg border bg-black text-white shadow-sm overflow-hidden">
      {/* Video / Image area */}
      <div className="aspect-[9/16] max-h-96 bg-gray-900 relative">
        {imageUrl ? (
          <img src={imageUrl} alt="Ad preview" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <ImageIcon className="h-12 w-12 text-gray-600" />
          </div>
        )}

        {/* Overlay content */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 space-y-2">
          <p className="text-sm font-semibold">@{userName ?? "tu_negocio"}</p>
          <p className="text-xs line-clamp-3 whitespace-pre-line">{copy}</p>

          <Button className="w-full bg-green-600 hover:bg-green-700 text-white text-xs h-8">
            <MessageCircle className="h-3 w-3 mr-1" />
            {cta ?? "Enviar mensaje por WhatsApp"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export function AdPreview({ platform, ...props }: AdPreviewProps) {
  return (
    <div className={cn("flex justify-center")}>
      {platform === "facebook" && <FacebookPreview {...props} />}
      {platform === "instagram" && <InstagramPreview {...props} />}
      {platform === "tiktok" && <TikTokPreview {...props} />}
    </div>
  )
}
