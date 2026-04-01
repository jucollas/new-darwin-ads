import { create } from "zustand"
import api from "../lib/api"
import { ENDPOINTS } from "../lib/endpoints"
import type { User } from "../types"

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  loadUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem("token"),
  isAuthenticated: !!localStorage.getItem("token"),

  login: async (email, password) => {
    const { data } = await api.post(ENDPOINTS.auth.login, { email, password })
    localStorage.setItem("token", data.access_token)
    set({ token: data.access_token, isAuthenticated: true, user: data.user ?? null })
  },

  register: async (email, password, name) => {
    const { data } = await api.post(ENDPOINTS.auth.register, {
      email,
      password,
      name,
    })
    localStorage.setItem("token", data.access_token)
    set({ token: data.access_token, isAuthenticated: true, user: data.user ?? null })
  },

  logout: () => {
    localStorage.removeItem("token")
    set({ token: null, isAuthenticated: false, user: null })
  },

  loadUser: async () => {
    try {
      const { data } = await api.get(ENDPOINTS.auth.me)
      set({ user: data, isAuthenticated: true })
    } catch {
      localStorage.removeItem("token")
      set({ token: null, isAuthenticated: false, user: null })
    }
  },
}))
