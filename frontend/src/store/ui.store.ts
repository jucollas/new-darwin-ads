import { create } from "zustand"

interface ConfirmDialog {
  title: string
  message: string
  onConfirm: () => void
}

interface UIState {
  sidebarOpen: boolean
  confirmDialog: ConfirmDialog | null
  toggleSidebar: () => void
  closeSidebar: () => void
  openConfirmDialog: (opts: ConfirmDialog) => void
  closeConfirmDialog: () => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  confirmDialog: null,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  closeSidebar: () => set({ sidebarOpen: false }),

  openConfirmDialog: (opts) => set({ confirmDialog: opts }),

  closeConfirmDialog: () => set({ confirmDialog: null }),
}))
