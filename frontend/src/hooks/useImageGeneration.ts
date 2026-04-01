import { useState, useCallback } from "react"
import api from "../lib/api"
import { ENDPOINTS } from "../lib/endpoints"
import type { GenerateImageResponse } from "../types"

export function useImageGeneration() {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)

  const generate = useCallback(
    async (params: {
      prompt: string
      aspect_ratio: "1:1" | "9:16"
      campaign_id: string
      proposal_id: string
    }) => {
      setImageUrl(null)
      setIsGenerating(true)

      try {
        const { data } = await api.post<GenerateImageResponse>(
          ENDPOINTS.images.generate,
          params,
        )
        setImageUrl(data.image_url)
      } catch {
        // error handled by caller
      } finally {
        setIsGenerating(false)
      }
    },
    [],
  )

  const reset = useCallback(() => {
    setImageUrl(null)
    setIsGenerating(false)
  }, [])

  return { generate, imageUrl, isGenerating, reset }
}
