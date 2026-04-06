import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Megaphone, Dna, User, X, Plug } from 'lucide-react'
import { useUIStore } from '@/store/ui.store'
import { Button } from '@/components/ui/button'

const sidebarLinks = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/campaigns', label: 'Campañas', icon: Megaphone },
  { to: '/genetic', label: 'Algoritmo Genético', icon: Dna },
  { to: '/settings/meta-connect', label: 'Meta Ads', icon: Plug },
  { to: '/profile', label: 'Perfil', icon: User },
]

export function Sidebar() {
  const { sidebarOpen, closeSidebar } = useUIStore()

  return (
    <>
      {/* Overlay on mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-14 left-0 z-40 h-[calc(100vh-3.5rem)] w-64 border-r bg-card transition-transform duration-300 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Close button */}
        <div className="flex items-center justify-end p-2">
          <Button variant="ghost" size="icon" onClick={closeSidebar}>
            <X className="h-5 w-5" />
            <span className="sr-only">Cerrar menú</span>
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex flex-col gap-1 px-3 pb-4">
          {sidebarLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={closeSidebar}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`
              }
            >
              <link.icon className="h-5 w-5" />
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  )
}
