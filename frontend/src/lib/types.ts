/**
 * Shared TypeScript interfaces for Blitz AgentOS frontend.
 */

export interface UserSession {
  userId: string;
  email: string;
  username: string;
  roles: string[];
  /** Stored in server-side session ONLY — never sent to the browser. */
  accessToken: string;
}

export interface ApiError {
  detail: string;
  permission_required?: string;
  user_roles?: string[];
  hint?: string;
}
