/**
 * Next.js Edge Runtime middleware for route protection.
 *
 * Strategy: allowlist approach — every route is protected by default.
 * Public routes (login, next-auth callbacks, static assets) are explicitly
 * listed and pass through without authentication.
 *
 * CVE-2025-29927 mitigation: Next.js 15.5.12 >= 15.2.3 required — verified
 * in package.json. This middleware is the canonical auth gate; no per-page
 * auth checks are needed.
 *
 * Session verification uses next-auth/jwt getToken() which decrypts the
 * next-auth session cookie (encrypted with NEXTAUTH_SECRET). Raw jose.jwtVerify()
 * cannot be used here because next-auth v5 encrypts the session JWT before
 * storing it in the cookie. jose is still required as a peer dependency of
 * next-auth/jwt for Edge Runtime compatibility.
 */
import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

// Public paths that do not require authentication.
// Add new public paths here — never add to the deny list.
const PUBLIC_PATHS = ["/login"];

// Public path prefixes — any path starting with these passes through.
const PUBLIC_PATH_PREFIXES = [
  "/api/auth/", // next-auth: /api/auth/callback/*, /api/auth/session, /api/auth/csrf, etc.
];

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.includes(pathname)) return true;
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname } = request.nextUrl;

  // Let public routes pass through unconditionally.
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Verify the next-auth session token. getToken() decrypts the encrypted
  // session cookie using NEXTAUTH_SECRET — Edge Runtime compatible via jose.
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET ?? process.env.AUTH_SECRET,
  });

  if (!token) {
    // No valid session — redirect to /login, preserving the intended destination
    // so the user is returned to the original page after sign-in.
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Session error tokens indicate expired sessions or token refresh failures.
  // Force re-authentication so stale/invalid tokens are never silently accepted.
  if (token.error) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    loginUrl.searchParams.set("error", token.error as string);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

/**
 * Matcher excludes Next.js internals and static asset extensions from
 * middleware processing to avoid unnecessary JWT verification on every
 * image, font, and JS chunk request.
 *
 * Static assets are served directly by Next.js without hitting this
 * middleware, which improves performance significantly.
 */
export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
