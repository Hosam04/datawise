'use client'

import { useEffect, useState } from 'react'
import { Download, Monitor, Moon, Sun, Database, FileText } from 'lucide-react'
import { useTheme } from 'next-themes'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  APP_VERSION,
  downloadAppData,
} from '@/lib/app-data'
import { deleteAllDatasetsApi, deleteAllReportsApi } from '@/lib/api'
import { useDatasetStore } from '@/stores/dataset-store'
import { useReportStore } from '@/stores/report-store'

const themeOptions = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
] as const

function SettingsSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </section>
  )
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const id = window.requestAnimationFrame(() => setMounted(true))
    return () => window.cancelAnimationFrame(id)
  }, [])

  const handleExport = () => {
    downloadAppData()
    toast.success('Data exported', {
      description: 'Your DataWise data was downloaded as JSON.',
    })
  }

  const clearLocalDatasets = useDatasetStore((state) => state.datasets.length > 0)
  const clearLocalReports = useReportStore((state) => state.reports.length > 0)

  const handleCleanDatasets = async () => {
    try {
      await deleteAllDatasetsApi()
      useDatasetStore.setState({ datasets: [] })
      toast.success('Datasets cleaned', {
        description: 'All datasets removed from database and local storage.',
      })
    } catch (error) {
      console.error('Failed to clean datasets:', error)
      toast.error('Failed to clean datasets', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    }
  }

  const handleCleanReports = async () => {
    try {
      await deleteAllReportsApi()
      useReportStore.setState({ reports: [] })
      toast.success('Reports cleaned', {
        description: 'All reports removed from database and local storage.',
      })
    } catch (error) {
      console.error('Failed to clean reports:', error)
      toast.error('Failed to clean reports', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="mt-2 text-muted-foreground">
          Manage appearance, data, and app information.
        </p>
      </div>

      <SettingsSection
        title="Appearance"
        description="Choose how DataWise looks on your device."
      >
        <div className="flex flex-wrap gap-2">
          {themeOptions.map((option) => {
            const Icon = option.icon
            const isActive = mounted && theme === option.value

            return (
              <button
                key={option.value}
                type="button"
                disabled={!mounted}
                aria-pressed={isActive}
                onClick={() => setTheme(option.value)}
                className={cn(
                  'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'border border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <Icon className="size-4" />
                {option.label}
              </button>
            )
          })}
        </div>
      </SettingsSection>

      <SettingsSection
        title="Data"
        description="Export or reset your local application data."
      >
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={handleExport}>
            <Download className="size-4" />
            Export data as JSON
          </Button>

          <ConfirmDialog
            title="Clean all datasets?"
            description="This will permanently remove all datasets from the database and local storage. Reports will NOT be deleted. This action cannot be undone."
            confirmLabel="Clean datasets"
            onConfirm={handleCleanDatasets}
            disabled={!clearLocalDatasets}
            trigger={
              <Button variant="destructive" disabled={!clearLocalDatasets}>
                <Database className="size-4" />
                Clean Datasets
              </Button>
            }
          />

          <ConfirmDialog
            title="Clean all reports?"
            description="This will permanently remove all reports from the database and local storage. This action cannot be undone."
            confirmLabel="Clean reports"
            onConfirm={handleCleanReports}
            disabled={!clearLocalReports}
            trigger={
              <Button variant="destructive" disabled={!clearLocalReports}>
                <FileText className="size-4" />
                Clean Reports
              </Button>
            }
          />
        </div>
      </SettingsSection>

      <SettingsSection title="About">
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <span className="text-muted-foreground">Application</span>
            <span className="font-medium text-foreground">DataWise</span>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <span className="text-muted-foreground">Version</span>
            <span className="font-medium text-foreground">{APP_VERSION}</span>
          </div>

          <p className="leading-6 text-muted-foreground">
            DataWise is an AI-powered data analysis and visualization platform.
            Data is stored locally in your browser.
          </p>
        </div>
      </SettingsSection>
    </div>
  )
}
