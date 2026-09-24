import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuthStore } from '@/stores/auth-store'

export function useRequireAuth() {
  const router = useRouter()
  const pathname = usePathname()
  const { user, isLoaded, accessToken } = useAuthStore()
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    // Wait for store to be loaded from persistence
    if (!isLoaded) {
      return
    }

    // Don't check auth on login/signup pages
    if (pathname === '/login' || pathname === '/signup') {
      setIsChecking(false)
      return
    }

    // Check if user is authenticated
    if (!user?.email || !accessToken) {
      router.push('/login')
      return
    }

    setIsChecking(false)
  }, [isLoaded, user, accessToken, pathname, router])

  return !isChecking && !!user?.email && !!accessToken
}
