import { useUIStore } from "@/store/ui.store"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export function ConfirmDialog() {
  const confirmDialog = useUIStore((s) => s.confirmDialog)
  const closeConfirmDialog = useUIStore((s) => s.closeConfirmDialog)

  const handleConfirm = () => {
    confirmDialog?.onConfirm()
    closeConfirmDialog()
  }

  return (
    <Dialog
      open={confirmDialog !== null}
      onOpenChange={(open) => {
        if (!open) closeConfirmDialog()
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{confirmDialog?.title}</DialogTitle>
          <DialogDescription>{confirmDialog?.message}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={closeConfirmDialog}>
            Cancelar
          </Button>
          <Button variant="destructive" onClick={handleConfirm}>
            Confirmar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
