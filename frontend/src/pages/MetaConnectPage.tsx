import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"
import { Loader2, Plug, Trash2, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useUIStore } from "@/store/ui.store"
import { useAdAccounts, useDeleteAdAccount } from "@/hooks/usePublishing"
import { getMetaLoginUrl, verifyAdAccount } from "@/lib/api"

export default function MetaConnectPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: accounts, isLoading } = useAdAccounts()
  const deleteMutation = useDeleteAdAccount()
  const openConfirmDialog = useUIStore((s) => s.openConfirmDialog)
  const [tokenStatus, setTokenStatus] = useState<
    Record<string, "valid" | "invalid" | "checking">
  >({})

  const handleVerify = async (id: string) => {
    setTokenStatus((prev) => ({ ...prev, [id]: "checking" }))
    try {
      const { data } = await verifyAdAccount(id)
      setTokenStatus((prev) => ({ ...prev, [id]: data.is_valid ? "valid" : "invalid" }))
      if (data.is_valid) {
        toast.success("Token válido")
      } else {
        toast.error(data.message || "Token expirado o inválido")
      }
    } catch {
      setTokenStatus((prev) => ({ ...prev, [id]: "invalid" }))
      toast.error("Error al verificar el token")
    }
  }

  // Handle OAuth return
  useEffect(() => {
    const oauth = searchParams.get("oauth")
    if (oauth === "success") {
      toast.success("Cuenta de Meta conectada correctamente")
      searchParams.delete("oauth")
      setSearchParams(searchParams, { replace: true })
    } else if (oauth === "error") {
      const message = searchParams.get("message") || "Error al conectar con Meta"
      toast.error(message)
      searchParams.delete("oauth")
      searchParams.delete("message")
      setSearchParams(searchParams, { replace: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleConnect = async () => {
    try {
      const { data } = await getMetaLoginUrl()
      if (data.login_url && data.login_url.startsWith("https://www.facebook.com/")) {
        window.location.href = data.login_url
      } else {
        toast.error("La URL de conexión no es válida. Verifica que el publishing-service esté activo.")
      }
    } catch {
      toast.error("Error al obtener la URL de conexión")
    }
  }

  const handleDisconnect = (id: string) => {
    openConfirmDialog({
      title: "Desconectar cuenta",
      message: "¿Estás seguro de que deseas desconectar esta cuenta de Meta Ads?",
      onConfirm: () => deleteMutation.mutate(id),
    })
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48" />
      </div>
    )
  }

  const hasAccounts = accounts && accounts.length > 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Conecta tu cuenta de Meta Ads</h1>
        <p className="text-muted-foreground mt-1">
          Para publicar anuncios necesitas conectar tu cuenta de Meta
        </p>
      </div>

      {!hasAccounts ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Plug className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-6">
              No tienes ninguna cuenta conectada
            </p>
            <Button size="lg" onClick={handleConnect}>
              <Plug className="mr-2 h-5 w-5" />
              Conectar con Meta
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {accounts.map((account) => (
            <Card key={account.id}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-base font-medium">
                  {account.meta_ad_account_id}
                </CardTitle>
                <div className="flex items-center gap-2">
                  {tokenStatus[account.id] === "valid" && (
                    <Badge variant="default" className="bg-green-600">
                      Token válido
                    </Badge>
                  )}
                  {tokenStatus[account.id] === "invalid" && (
                    <Badge variant="destructive">Token inválido</Badge>
                  )}
                  {!tokenStatus[account.id] && (
                    <Badge variant="outline">Sin verificar</Badge>
                  )}
                  <Badge variant={account.is_active ? "default" : "secondary"}>
                    {account.is_active ? "Activa" : "Inactiva"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="flex items-center justify-between">
                <div className="space-y-1 text-sm text-muted-foreground">
                  <p>Page ID: {account.meta_page_id}</p>
                  {account.whatsapp_phone_number && (
                    <p>WhatsApp: {account.whatsapp_phone_number}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleVerify(account.id)}
                    disabled={tokenStatus[account.id] === "checking"}
                  >
                    {tokenStatus[account.id] === "checking" ? (
                      <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    ) : (
                      <ShieldCheck className="mr-1 h-4 w-4" />
                    )}
                    Verificar
                  </Button>
                  {tokenStatus[account.id] === "invalid" && (
                    <Button size="sm" onClick={handleConnect}>
                      <Plug className="mr-1 h-4 w-4" />
                      Reconectar
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDisconnect(account.id)}
                    disabled={deleteMutation.isPending}
                  >
                    {deleteMutation.isPending ? (
                      <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="mr-1 h-4 w-4" />
                    )}
                    Desconectar
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}

          <Button variant="outline" onClick={handleConnect}>
            <Plug className="mr-2 h-4 w-4" />
            Conectar otra cuenta
          </Button>
        </div>
      )}
    </div>
  )
}
