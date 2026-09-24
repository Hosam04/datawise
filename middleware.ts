import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = ['/', '/_next', '/api', '/public']

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname

  if (PUBLIC_PATHS.some(path => pathname.startsWith(path)) || pathname === '') {
    return NextResponse.next()
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next|api).*)'],
}
