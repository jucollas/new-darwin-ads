import { ReactNode } from "react"
import { render, type RenderOptions } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import type { Proposal } from "@/types"

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

function TestProviders({ children }: { children: ReactNode }) {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

export function renderWithProviders(
  ui: ReactNode,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return render(ui, { wrapper: TestProviders, ...options })
}

export function createMockProposal(
  overrides: Partial<Proposal> = {},
): Proposal {
  return {
    id: "prop-1",
    campaign_id: "camp-1",
    copy_text: "Test ad copy text for the proposal",
    script: "Test script for the video ad",
    image_prompt: "A beautiful landscape with mountains",
    target_audience: {
      age_min: 25,
      age_max: 35,
      genders: ["female"],
      interests: ["fitness", "running"],
      locations: ["CO", "MX"],
    },
    cta_type: "whatsapp_chat",
    whatsapp_number: "+573001234567",
    is_selected: false,
    is_edited: false,
    image_url: null,
    created_at: "2026-03-01T12:00:00Z",
    ...overrides,
  }
}
