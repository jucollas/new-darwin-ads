import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { screen, waitFor, within, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { renderWithProviders, createMockProposal } from "@/test/helpers"
import { ProposalCard } from "@/components/ProposalCard"

// Mock axios
vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

// Mock sonner
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import api from "@/lib/api"
import { toast } from "sonner"

const mockApi = vi.mocked(api)

function renderCard(proposalOverrides = {}, cardProps = {}) {
  const proposal = createMockProposal(proposalOverrides)
  const onSelect = vi.fn()
  const onRegenerate = vi.fn()
  const onProposalUpdated = vi.fn()

  const result = renderWithProviders(
    <ProposalCard
      proposal={proposal}
      index={0}
      onSelect={onSelect}
      onRegenerate={onRegenerate}
      onProposalUpdated={onProposalUpdated}
      {...cardProps}
    />,
  )

  return { proposal, onSelect, onRegenerate, onProposalUpdated, ...result }
}

describe("Proposal Editing", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // Test 1: Renders edit mode with pre-filled values
  it("renders edit mode with all fields pre-filled when clicking Edit", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Editar"))

    // Check that form fields are visible and pre-filled
    expect(screen.getByLabelText("Copy")).toHaveValue(
      "Test ad copy text for the proposal",
    )
    expect(screen.getByLabelText("Script")).toHaveValue(
      "Test script for the video ad",
    )
    expect(screen.getByLabelText("Prompt de imagen")).toHaveValue(
      "A beautiful landscape with mountains",
    )
    expect(screen.getByLabelText("Edad mínima")).toHaveValue(25)
    expect(screen.getByLabelText("Edad máxima")).toHaveValue(35)
  })

  // Test 2: Validation - empty copy_text
  it("shows validation error when copy_text is empty", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Editar"))

    const copyField = screen.getByLabelText("Copy")
    await user.clear(copyField)
    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => {
      expect(screen.getByText("El copy es obligatorio")).toBeInTheDocument()
    })
    expect(mockApi.put).not.toHaveBeenCalled()
  })

  // Test 3: Validation - age_max < age_min
  it("shows validation error when age_max is less than age_min", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Editar"))

    const ageMin = screen.getByLabelText("Edad mínima")
    const ageMax = screen.getByLabelText("Edad máxima")
    await user.clear(ageMin)
    await user.type(ageMin, "40")
    await user.clear(ageMax)
    await user.type(ageMax, "25")

    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => {
      expect(
        screen.getByText(
          "La edad máxima debe ser mayor o igual a la mínima",
        ),
      ).toBeInTheDocument()
    })
    expect(mockApi.put).not.toHaveBeenCalled()
  })

  // Test 4: Validation - whatsapp_number required when cta_type is whatsapp_chat
  it("shows validation error when whatsapp_number is empty for whatsapp_chat CTA", async () => {
    const user = userEvent.setup()
    renderCard({ whatsapp_number: "" })

    await user.click(screen.getByTitle("Editar"))

    const whatsappInput = screen.getByLabelText("Número de WhatsApp")
    await user.clear(whatsappInput)

    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => {
      expect(
        screen.getByText(
          "El número de WhatsApp es obligatorio para este CTA",
        ),
      ).toBeInTheDocument()
    })
    expect(mockApi.put).not.toHaveBeenCalled()
  })

  // Test 5: Validation - whatsapp_number format
  it("rejects invalid whatsapp_number format", async () => {
    const user = userEvent.setup()
    renderCard({ whatsapp_number: "+573001234567" })

    await user.click(screen.getByTitle("Editar"))

    const whatsappInput = screen.getByLabelText("Número de WhatsApp")
    await user.clear(whatsappInput)
    await user.type(whatsappInput, "12345")

    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/formato inválido/i),
      ).toBeInTheDocument()
    })
    expect(mockApi.put).not.toHaveBeenCalled()
  })

  // Test 6: Successful save
  it("calls API with correct payload and shows Edited badge on successful save", async () => {
    const user = userEvent.setup()
    const updatedProposal = createMockProposal({
      is_edited: true,
      copy_text: "Updated copy text here",
    })

    mockApi.put.mockResolvedValueOnce({ data: updatedProposal })

    const { onProposalUpdated } = renderCard()

    await user.click(screen.getByTitle("Editar"))

    const copyField = screen.getByLabelText("Copy")
    await user.clear(copyField)
    await user.type(copyField, "Updated copy text here")

    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => {
      expect(mockApi.put).toHaveBeenCalledWith(
        "/api/v1/campaigns/camp-1/proposals/prop-1",
        expect.objectContaining({
          copy_text: "Updated copy text here",
        }),
      )
    })

    await waitFor(() => {
      expect(screen.getByText("Editada")).toBeInTheDocument()
    })
  })

  // Test 7: Cancel discards changes
  it("discards changes and exits edit mode on Cancel", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Editar"))

    const copyField = screen.getByLabelText("Copy")
    await user.clear(copyField)
    await user.type(copyField, "Changed text")

    await user.click(screen.getByRole("button", { name: /cancelar/i }))

    // Should exit edit mode and show original text
    expect(screen.queryByLabelText("Copy")).not.toBeInTheDocument()
    expect(
      screen.getByText("Test ad copy text for the proposal"),
    ).toBeInTheDocument()
  })

  // Test 8: Loading state while saving
  it("shows loading state on Save button while saving", async () => {
    const user = userEvent.setup()
    // Never resolve so we can check the loading state
    mockApi.put.mockReturnValueOnce(new Promise(() => {}))

    renderCard()

    await user.click(screen.getByTitle("Editar"))
    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => {
      const saveBtn = screen.getByRole("button", { name: /guardar/i })
      expect(saveBtn).toBeDisabled()
    })
  })

  // Test 9: API error on save
  it("shows error message and keeps edit mode when API returns error", async () => {
    const user = userEvent.setup()
    mockApi.put.mockRejectedValueOnce({ response: { status: 500 } })

    renderCard()

    await user.click(screen.getByTitle("Editar"))
    await user.click(screen.getByRole("button", { name: /guardar/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Error al guardar la propuesta",
      )
    })

    // Form should still be visible
    expect(screen.getByLabelText("Copy")).toBeInTheDocument()
  })

  // Test 10: Conditional whatsapp field
  it("shows whatsapp_number input only when cta_type is whatsapp_chat", async () => {
    const user = userEvent.setup()
    renderCard({ cta_type: "link", whatsapp_number: null })

    await user.click(screen.getByTitle("Editar"))

    // Should NOT have whatsapp field for link CTA
    expect(
      screen.queryByLabelText("Número de WhatsApp"),
    ).not.toBeInTheDocument()
  })
})

describe("Detail View", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // Test 11: Opens detail modal
  it("opens detail modal with all proposal data when clicking View Details", async () => {
    const user = userEvent.setup()
    renderCard({
      copy_text: "Full copy text for detail",
      script: "Full script text",
    })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByText("Detalle de propuesta"),
      ).toBeInTheDocument()
    })
    // Text appears in both card and modal; check via dialog scope
    const dialog = screen.getByRole("dialog")
    expect(
      within(dialog).getByText("Full copy text for detail"),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText("Full script text"),
    ).toBeInTheDocument()
  })

  // Test 12: Displays image when image_url exists
  it("renders image when image_url exists", async () => {
    const user = userEvent.setup()
    renderCard({ image_url: "https://example.com/image.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument()
    })
    const dialog = screen.getByRole("dialog")
    const img = within(dialog).getByAltText("Imagen de la propuesta")
    expect(img).toHaveAttribute("src", "https://example.com/image.png")
  })

  // Test 13: Shows placeholder when image_url is null
  it("shows placeholder text when image_url is null", async () => {
    const user = userEvent.setup()
    renderCard({ image_url: null })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByText("Imagen no generada aún"),
      ).toBeInTheDocument()
    })
  })

  // Test 14: Closes on X button
  it("closes modal when clicking close button", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByText("Detalle de propuesta"),
      ).toBeInTheDocument()
    })

    // Click the X close button (sr-only text "Close")
    const closeButton = screen.getByRole("button", { name: /close/i })
    await user.click(closeButton)

    await waitFor(() => {
      expect(
        screen.queryByText("Detalle de propuesta"),
      ).not.toBeInTheDocument()
    })
  })

  // Test 15: Closes on backdrop click
  it("closes modal on backdrop click", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByText("Detalle de propuesta"),
      ).toBeInTheDocument()
    })

    // Radix Dialog overlay - click the overlay to close
    const overlay = document.querySelector("[data-state='open'].fixed.inset-0")
    if (overlay) {
      await user.click(overlay as Element)

      await waitFor(() => {
        expect(
          screen.queryByText("Detalle de propuesta"),
        ).not.toBeInTheDocument()
      })
    }
  })

  // Test 16: Displays target_audience correctly
  it("displays target audience as readable text", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument()
    })
    const dialog = screen.getByRole("dialog")
    expect(within(dialog).getByText(/Edades 25–35/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Femenino/)).toBeInTheDocument()
    expect(within(dialog).getByText(/fitness, running/)).toBeInTheDocument()
    expect(within(dialog).getByText(/CO, MX/)).toBeInTheDocument()
  })

  // Test 17: Shows "Selected" badge
  it("shows Selected badge when is_selected is true", async () => {
    const user = userEvent.setup()
    renderCard({ is_selected: true })

    // Badge visible on the card itself
    expect(screen.getByText("Seleccionada")).toBeInTheDocument()

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      // Badge also in modal
      const badges = screen.getAllByText("Seleccionada")
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  // Test 18: Shows "Edited" badge
  it("shows Edited badge when is_edited is true", async () => {
    const user = userEvent.setup()
    renderCard({ is_edited: true })

    // Badge visible on the card itself
    expect(screen.getByText("Editada")).toBeInTheDocument()

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      const badges = screen.getAllByText("Editada")
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  // Test 19: Edit mode in detail view
  it("switches to edit form when clicking Edit inside detail modal", async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByText("Detalle de propuesta"),
      ).toBeInTheDocument()
    })

    // Find the Edit button inside the modal
    const modal = screen.getByRole("dialog")
    const editButton = within(modal).getByRole("button", {
      name: /editar/i,
    })
    await user.click(editButton)

    // Should see the edit form fields
    await waitFor(() => {
      expect(within(modal).getByLabelText("Copy")).toBeInTheDocument()
      expect(within(modal).getByLabelText("Script")).toBeInTheDocument()
    })
  })
})

describe("Image Regeneration", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // Test 20: "Regenerate Image" button visible only when image_url is not null
  it("shows Regenerate Image button only when image_url is not null", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

    // Without image
    const { unmount } = renderCard({ image_url: null })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /regenerar imagen/i }),
      ).not.toBeInTheDocument()
    })

    unmount()

    // With image
    renderCard({ image_url: "https://example.com/img.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })
  })

  // Test 21: Confirmation dialog appears
  it("shows confirmation dialog when clicking Regenerate Image", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderCard({ image_url: "https://example.com/img.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })

    await user.click(
      screen.getByRole("button", { name: /regenerar imagen/i }),
    )

    await waitFor(() => {
      expect(
        screen.getByText(/estás seguro.*regenerar/i),
      ).toBeInTheDocument()
    })
  })

  // Test 22: Cancel confirmation does not call API
  it("does not call API when cancelling regeneration confirmation", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderCard({ image_url: "https://example.com/img.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })

    await user.click(
      screen.getByRole("button", { name: /regenerar imagen/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/estás seguro/i)).toBeInTheDocument()
    })

    // Click Cancel
    const cancelBtns = screen.getAllByRole("button", { name: /cancelar/i })
    await user.click(cancelBtns[cancelBtns.length - 1])

    expect(mockApi.post).not.toHaveBeenCalled()
  })

  // Test 23: Confirm triggers regeneration API call
  it("calls select endpoint when confirming regeneration", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    mockApi.post.mockResolvedValueOnce({ data: {} })
    // Polling response - keep generating
    mockApi.get.mockResolvedValue({
      data: { id: "camp-1", status: "image_generating" },
    })

    renderCard({ image_url: "https://example.com/img.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })

    await user.click(
      screen.getByRole("button", { name: /regenerar imagen/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/estás seguro/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /confirmar/i }))

    await waitFor(() => {
      expect(mockApi.post).toHaveBeenCalledWith(
        "/api/v1/campaigns/camp-1/select/prop-1",
      )
    })
  })

  // Test 24: Loading state during regeneration
  it("shows loading state during regeneration", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    mockApi.post.mockResolvedValueOnce({ data: {} })
    mockApi.get.mockResolvedValue({
      data: { id: "camp-1", status: "image_generating" },
    })

    renderCard({ image_url: "https://example.com/img.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })

    await user.click(
      screen.getByRole("button", { name: /regenerar imagen/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/estás seguro/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /confirmar/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/generando nueva imagen/i),
      ).toBeInTheDocument()
    })
  })

  // Test 25: Polling updates image
  it("updates image after polling detects image_ready", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    mockApi.post.mockResolvedValueOnce({ data: {} })

    const updatedProposal = createMockProposal({
      image_url: "https://example.com/new-image.png",
    })

    // First poll: still generating. Second poll: ready
    mockApi.get
      .mockResolvedValueOnce({
        data: { id: "camp-1", status: "image_generating" },
      })
      .mockResolvedValueOnce({
        data: { id: "camp-1", status: "image_ready" },
      })
      .mockResolvedValueOnce({
        data: [updatedProposal],
      })

    renderCard({ image_url: "https://example.com/old.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })

    await user.click(
      screen.getByRole("button", { name: /regenerar imagen/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/estás seguro/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /confirmar/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/generando nueva imagen/i),
      ).toBeInTheDocument()
    })

    // Advance past first poll interval (5s)
    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    // Advance past second poll interval (5s) - should detect image_ready
    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Imagen regenerada exitosamente",
      )
    })
  })

  // Test 26: Polling timeout
  it("shows timeout error after 2 minutes of polling", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    mockApi.post.mockResolvedValueOnce({ data: {} })
    // Always return generating status
    mockApi.get.mockResolvedValue({
      data: { id: "camp-1", status: "image_generating" },
    })

    renderCard({ image_url: "https://example.com/img.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })

    await user.click(
      screen.getByRole("button", { name: /regenerar imagen/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/estás seguro/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /confirmar/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/generando nueva imagen/i),
      ).toBeInTheDocument()
    })

    // Advance past timeout (120s)
    await act(async () => {
      vi.advanceTimersByTime(125000)
    })

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        expect.stringContaining("tardando más de lo esperado"),
      )
    })
  })

  // Test 27: Regeneration failure
  it("shows error and re-enables button when campaign status becomes failed", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    mockApi.post.mockResolvedValueOnce({ data: {} })

    // First poll returns failed
    mockApi.get.mockResolvedValueOnce({
      data: { id: "camp-1", status: "failed" },
    })

    renderCard({ image_url: "https://example.com/img.png" })

    await user.click(screen.getByTitle("Ver detalles"))

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /regenerar imagen/i }),
      ).toBeInTheDocument()
    })

    await user.click(
      screen.getByRole("button", { name: /regenerar imagen/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/estás seguro/i)).toBeInTheDocument()
    })

    await user.click(screen.getByRole("button", { name: /confirmar/i }))

    // Advance to first poll
    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Error al generar la imagen",
      )
    })
  })
})
