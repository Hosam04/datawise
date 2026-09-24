import { DashboardShell } from '@/components/datawise/dashboard-shell'

export default function DashboardLayout({
  children,
}: LayoutProps<'/'>) {
  return <DashboardShell>{children}</DashboardShell>
}
