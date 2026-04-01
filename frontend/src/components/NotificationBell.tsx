import { useState, useRef, useEffect } from "react"
import { Bell } from "lucide-react"
import { useQuery, useMutation } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import type { Notification } from "@/types"

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const { data: unreadCount = 0 } = useQuery<number>({
    queryKey: ["notifications-unread-count"],
    queryFn: async () => {
      const { data } = await api.get(ENDPOINTS.notifications.unreadCount)
      return typeof data === "number" ? data : data.count ?? 0
    },
    refetchInterval: 30000,
  })

  const { data: notifications = [] } = useQuery<Notification[]>({
    queryKey: ["notifications"],
    queryFn: async () => {
      const { data } = await api.get(ENDPOINTS.notifications.list)
      return Array.isArray(data) ? data : data.items ?? []
    },
    enabled: open,
    refetchInterval: open ? 30000 : false,
  })

  const markReadMutation = useMutation({
    mutationFn: (id: string) =>
      api.put(ENDPOINTS.notifications.markRead(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications-unread-count"] })
      queryClient.invalidateQueries({ queryKey: ["notifications"] })
    },
  })

  const latestFive = notifications.slice(0, 5)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        className="relative rounded-md p-2 hover:bg-accent transition-colors"
        onClick={() => setOpen(!open)}
        aria-label="Notificaciones"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 h-2.5 w-2.5 rounded-full bg-red-500" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-lg border bg-card shadow-lg z-50">
          <div className="p-3 border-b">
            <p className="text-sm font-semibold">Notificaciones</p>
          </div>
          {latestFive.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              No hay notificaciones
            </div>
          ) : (
            <ul className="max-h-72 overflow-y-auto">
              {latestFive.map((notification) => (
                <li
                  key={notification.id}
                  className={cn(
                    "border-b last:border-0 p-3 text-sm cursor-pointer",
                    !notification.is_read && "bg-accent/50"
                  )}
                  onClick={() => {
                    if (!notification.is_read) {
                      markReadMutation.mutate(notification.id)
                    }
                  }}
                >
                  <p className="font-medium">{notification.title}</p>
                  <p className="text-muted-foreground">{notification.body}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(notification.created_at).toLocaleDateString("es-ES", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
