import { useForm, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Link } from "react-router-dom"
import { Loader2, Plug } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useAdAccounts, usePublishCampaign } from "@/hooks/usePublishing"

const publishSchema = z.object({
  ad_account_id: z.string().min(1, "Selecciona una cuenta"),
  budget: z
    .number({ invalid_type_error: "Ingresa un monto válido" })
    .min(10000, "El presupuesto mínimo es $10,000 COP"),
})

type PublishFormValues = z.infer<typeof publishSchema>

interface PublishDialogProps {
  campaignId: string
  proposalId: string
  isOpen: boolean
  onClose: () => void
}

export function PublishDialog({
  campaignId,
  proposalId,
  isOpen,
  onClose,
}: PublishDialogProps) {
  const { data: accounts, isLoading: accountsLoading } = useAdAccounts()
  const publishMutation = usePublishCampaign()

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<PublishFormValues>({
    resolver: zodResolver(publishSchema),
    defaultValues: { ad_account_id: "", budget: undefined },
  })

  const activeAccounts = accounts?.filter((a) => a.is_active) ?? []

  const onSubmit = (values: PublishFormValues) => {
    publishMutation.mutate(
      {
        campaign_id: campaignId,
        proposal_id: proposalId,
        ad_account_id: values.ad_account_id,
        budget_daily_cents: values.budget * 100,
      },
      {
        onSuccess: () => {
          reset()
          onClose()
        },
      },
    )
  }

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      reset()
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Publicar campaña</DialogTitle>
          <DialogDescription>
            Selecciona la cuenta y el presupuesto diario para publicar en Meta Ads
          </DialogDescription>
        </DialogHeader>

        {accountsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : activeAccounts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Plug className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground mb-4">
              No tienes cuentas de Meta conectadas
            </p>
            <Button asChild variant="outline">
              <Link to="/settings/meta-connect">Conectar cuenta</Link>
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ad_account_id">Cuenta de Meta Ads</Label>
              <Controller
                control={control}
                name="ad_account_id"
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger>
                      <SelectValue placeholder="Selecciona una cuenta" />
                    </SelectTrigger>
                    <SelectContent>
                      {activeAccounts.map((account) => (
                        <SelectItem key={account.id} value={account.id}>
                          {account.meta_ad_account_id}
                          {account.whatsapp_phone_number
                            ? ` (${account.whatsapp_phone_number})`
                            : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.ad_account_id && (
                <p className="text-sm text-destructive">
                  {errors.ad_account_id.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="budget">Presupuesto diario (COP)</Label>
              <Input
                id="budget"
                type="number"
                placeholder="10000"
                {...register("budget", { valueAsNumber: true })}
              />
              {errors.budget && (
                <p className="text-sm text-destructive">
                  {errors.budget.message}
                </p>
              )}
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={publishMutation.isPending}>
                {publishMutation.isPending && (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                )}
                Publicar campaña
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
