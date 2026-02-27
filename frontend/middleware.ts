export { auth as middleware } from '@/auth';

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - /login (sign-in page)
     * - /api/auth/* (NextAuth handlers)
     * - /_next/* (Next.js internals)
     * - /favicon.ico, /sitemap.xml, etc.
     */
    '/((?!login|api/auth|_next|favicon.ico).*)',
  ],
};
