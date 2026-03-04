---
status: diagnosed
trigger: "callbackUrl missing from middleware redirect — unauthenticated /chat redirects to /login without ?callbackUrl=%2Fchat"
created: 2026-03-05T00:00:00Z
updated: 2026-03-05T00:30:00Z
---

## Current Focus

hypothesis: CONFIRMED — getToken() throws MissingSecret when session cookie exists but no secret is passed, bypassing the middleware redirect logic that sets callbackUrl
test: Traced getToken() source in @auth/core/jwt.js; confirmed secret is not auto-detected from env
expecting: N/A — root cause confirmed
next_action: Apply fix — pass NEXTAUTH_SECRET to getToken()

## Symptoms

expected: Visiting /chat while unauthenticated should redirect to /login?callbackUrl=%2Fchat
actual: Redirects to /login with no callbackUrl query parameter
errors: none visible (MissingSecret thrown internally in middleware, not surfaced to user)
reproduction: Visit http://localhost:3000/chat while logged out (specifically after a previous session expired — cookie exists)
started: unknown

## Eliminated

- hypothesis: URL constructor drops searchParams
  evidence: Verified with Node.js — new URL("/login", "http://localhost:3000/chat") + searchParams.set("callbackUrl", "/chat") produces correct URL http://localhost:3000/login?callbackUrl=%2Fchat
  timestamp: 2026-03-05T00:05:00Z

- hypothesis: NextResponse.redirect strips query params
  evidence: Tested NextResponse.redirect with URL containing query params — Location header preserves them correctly
  timestamp: 2026-03-05T00:06:00Z

- hypothesis: Competing redirect from login page or layout
  evidence: Login page uses useSearchParams() correctly; no router.push("/login") without params anywhere; no redirect in layout.tsx; no redirect in next.config.ts
  timestamp: 2026-03-05T00:07:00Z

- hypothesis: next-auth auth() in ChatPage auto-redirects to /login
  evidence: auth() in Server Components returns null when no session, does NOT redirect. The handleAuth() function is only used when auth() is used AS middleware.
  timestamp: 2026-03-05T00:10:00Z

- hypothesis: Middleware matcher regex excludes /chat
  evidence: Regex /((?!_next/static|_next/image|favicon.ico|.*\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*) matches /chat — negative lookahead passes because /chat doesn't match any exclusion
  timestamp: 2026-03-05T00:12:00Z

## Evidence

- timestamp: 2026-03-05T00:01:00Z
  checked: frontend/src/middleware.ts lines 47-52
  found: Redirect logic correctly constructs URL with callbackUrl=pathname
  implication: The code is correct IF it executes — issue must be in getToken() or something preventing this code from running

- timestamp: 2026-03-05T00:08:00Z
  checked: @auth/core/jwt.js (getToken source at node_modules/.pnpm/node_modules/@auth/core/jwt.js lines 85-109)
  found: getToken() requires explicit `secret` parameter. If cookie exists (line 97 check passes) but no secret provided (line 101), throws MissingSecret. No env var auto-detection for AUTH_SECRET/NEXTAUTH_SECRET in @auth/core 0.41.0.
  implication: When user has stale session cookie, getToken() throws instead of returning null, bypassing the callbackUrl redirect logic

- timestamp: 2026-03-05T00:09:00Z
  checked: middleware.ts line 45
  found: getToken({ req: request }) — NO secret parameter passed
  implication: For users with any session cookie (valid, expired, or stale), getToken() throws MissingSecret at @auth/core/jwt.js:101

- timestamp: 2026-03-05T00:10:00Z
  checked: next-auth/jwt.js
  found: Pure re-export of @auth/core/jwt — no wrapping, no secret auto-detection added
  implication: next-auth v5 beta.30 does NOT add env var detection to getToken() unlike v4

- timestamp: 2026-03-05T00:15:00Z
  checked: next-auth/lib/index.js (handleAuth function, lines 156-164)
  found: When used as middleware wrapper, next-auth redirects to signIn page (line 157: config.pages?.signIn ?? basePath/signin) with callbackUrl set to request.nextUrl.href. But this is NOT used by the custom middleware.
  implication: The custom middleware bypasses next-auth's built-in redirect-with-callbackUrl mechanism

- timestamp: 2026-03-05T00:20:00Z
  checked: @auth/core/jwt.js line 97-98, 101-102 control flow
  found: If no cookie -> returns null at line 98 (BEFORE secret check). If cookie exists -> needs secret at line 101 -> throws if missing.
  implication: Bug only manifests when session cookie exists (previous login). Brand-new users with zero cookies are NOT affected.

## Resolution

root_cause: |
  getToken() at middleware.ts:45 is called WITHOUT the `secret` parameter:
    `const token = await getToken({ req: request });`

  In @auth/core 0.41.0 (used by next-auth 5.0.0-beta.30), getToken() does NOT auto-detect
  AUTH_SECRET/NEXTAUTH_SECRET from environment variables (unlike next-auth v4).

  When a user has ANY session cookie (from a previous login):
  1. getToken() finds the cookie (jwt.js line 91: sessionStore.value is truthy)
  2. Passes the null check at line 97 (cookie exists)
  3. Hits line 101: `if (!secret) throw new MissingSecret(...)`
  4. MissingSecret propagates as unhandled error from middleware
  5. Next.js error handling takes over — redirects to /login WITHOUT callbackUrl

  For users with NO cookie (never logged in), getToken() returns null at line 98
  (before needing secret), so the middleware redirect WITH callbackUrl works correctly.

  This explains why the bug is intermittent — it only affects users who previously had a session.

fix: |
  Pass the secret to getToken() explicitly:

  ```typescript
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET ?? process.env.AUTH_SECRET,
  });
  ```

  This ensures getToken() can decrypt the session cookie (or return null for expired/invalid
  cookies) instead of throwing MissingSecret.

verification:
files_changed: []
