import { NotFoundView } from '@/components/datawise/not-found-view'

export default function SettingsNotFound() {
  return (
    <NotFoundView
      title="Settings not found"
      description="The settings page you requested does not exist."
      backHref="/settings"
      backLabel="Back to settings"
    />
  )
}
