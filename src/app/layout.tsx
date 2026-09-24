import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Geist } from 'next/font/google'
import './globals.css'
import { AppToaster } from '@/components/app-toaster'
import { ThemeProvider } from '@/components/theme-provider'


const _geistSans = Geist({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'DataWise - AI Data Analysis',
  description: 'AI-powered data analysis and visualization platform',
}

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: 'white' },
    { media: '(prefers-color-scheme: dark)', color: 'black' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<LayoutProps<'/'>>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased font-sans">
  <ThemeProvider>
    {children}
    <AppToaster />
  </ThemeProvider>

  {process.env.NODE_ENV === 'production' && <Analytics />}
    </body>
    </html>
  )
}
