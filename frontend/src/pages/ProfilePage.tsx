import { useNavigate } from "react-router-dom"
import { useQuery, useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/queryClient"
import api from "@/lib/api"
import { ENDPOINTS } from "@/lib/endpoints"
import { toast } from "sonner"
import { useAuthStore } from "@/store/auth.store"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import {
  User,
  Link2,
  LogOut,
  Loader2,
  CheckCircle,
  XCircle,
  Facebook,
  Camera,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { AdAccount } from "@/types"

const profileSchema = z.object({
  name: z.string().min(1, "El nombre es requerido"),
  whatsapp: z.string().optional(),
})

type ProfileFormValues = z.infer<typeof profileSchema>

export default function ProfilePage() {
  const navigate = useNavigate()
  const { user, logout, loadUser } = useAuthStore()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    values: user
      ? {
          name: user.name,
          whatsapp: user.whatsapp ?? "",
        }
      : undefined,
  })

  // Ad accounts (replaces meta connection status)
  const { data: adAccounts = [] } = useQuery<AdAccount[]>({
    queryKey: ["ad-accounts"],
    queryFn: () =>
      api.get(ENDPOINTS.publish.adAccounts).then((r) => {
        const body = r.data
        return Array.isArray(body) ? body : body.items ?? []
      }),
    enabled: !!user?.id,
  })

  const hasMetaConnection = adAccounts.length > 0

  const profileMutation = useMutation({
    mutationFn: (data: ProfileFormValues) =>
      api.patch(ENDPOINTS.auth.profile, data),
    onSuccess: () => {
      toast.success("Perfil actualizado")
      loadUser()
    },
    onError: () => toast.error("Error al actualizar perfil"),
  })

  const disconnectMutation = useMutation({
    mutationFn: (accountId: string) =>
      api.delete(ENDPOINTS.publish.adAccountDetail(accountId)),
    onSuccess: () => {
      toast.success("Cuenta desconectada")
      queryClient.invalidateQueries({ queryKey: ["ad-accounts"] })
    },
    onError: () => toast.error("Error al desconectar cuenta"),
  })

  const handleProfileSubmit = (data: ProfileFormValues) => {
    profileMutation.mutate(data)
  }

  const handleLogout = () => {
    logout()
    navigate("/login")
  }

  const handleConnectMeta = () => {
    window.location.href = `${import.meta.env.VITE_API_GATEWAY || ""}${ENDPOINTS.auth.metaConnect}`
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8 p-6">
      {/* Section 1: Personal Data */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            <CardTitle>Mi Perfil</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit(handleProfileSubmit)}
            className="space-y-6"
          >
            {/* Avatar */}
            <div className="flex items-center gap-4">
              <div className="relative group">
                <Avatar className="h-20 w-20">
                  <AvatarImage src={user?.avatar_url} alt={user?.name} />
                  <AvatarFallback className="text-lg">
                    {user?.name?.charAt(0).toUpperCase() ?? "U"}
                  </AvatarFallback>
                </Avatar>
                <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                  <Camera className="h-5 w-5 text-white" />
                </div>
              </div>
              <div>
                <p className="font-medium">{user?.name}</p>
                <p className="text-sm text-muted-foreground">{user?.email}</p>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Nombre</Label>
              <Input id="name" {...register("name")} />
              {errors.name && (
                <p className="text-sm text-red-500">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                value={user?.email ?? ""}
                readOnly
                disabled
                className="opacity-60"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="whatsapp">Número de WhatsApp</Label>
              <Input
                id="whatsapp"
                {...register("whatsapp")}
                placeholder="+52 1234567890"
              />
            </div>

            <Button type="submit" disabled={profileMutation.isPending}>
              {profileMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Guardar cambios
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Section 2: Meta Connection */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Link2 className="h-5 w-5 text-primary" />
            <CardTitle>Conexiones</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-blue-600 p-2">
                <Facebook className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="font-medium">Meta / Facebook</p>
                {hasMetaConnection ? (
                  <div className="flex items-center gap-1 text-sm text-green-500">
                    <CheckCircle className="h-3 w-3" />
                    {adAccounts.length} cuenta{adAccounts.length !== 1 ? "s" : ""} conectada{adAccounts.length !== 1 ? "s" : ""}
                  </div>
                ) : (
                  <div className="flex items-center gap-1 text-sm text-red-500">
                    <XCircle className="h-3 w-3" />
                    No conectado
                  </div>
                )}
              </div>
            </div>

            {!hasMetaConnection && (
              <Button size="sm" onClick={handleConnectMeta}>
                <Facebook className="h-4 w-4 mr-2" />
                Conectar con Meta
              </Button>
            )}
          </div>

          {hasMetaConnection && (
            <div className="space-y-2">
              {adAccounts.map((account) => (
                <div
                  key={account.id}
                  className="flex items-center justify-between rounded-lg bg-muted/50 p-3 text-sm"
                >
                  <div>
                    <span className="text-muted-foreground">Cuenta: </span>
                    <span className="font-medium">{account.meta_ad_account_id}</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => disconnectMutation.mutate(account.id)}
                    disabled={disconnectMutation.isPending}
                  >
                    Desconectar
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section 3: Logout */}
      <Separator />

      <div className="pb-8">
        <Button variant="destructive" onClick={handleLogout}>
          <LogOut className="h-4 w-4 mr-2" />
          Cerrar sesión
        </Button>
      </div>
    </div>
  )
}
