---
created: 2026-03-15T06:51:58.504Z
title: "Implement User Experience Enhancement (Topic #13)"
area: ui
priority: medium
target: v1.4-enhancement
effort: 6 weeks
existing_code: 25%
depends_on: ["topic-19-storage-service"]
design_doc: docs/enhancement/topics/13-user-experience-enhancement/00-specification.md
files:
  - frontend/src/app/(authenticated)/profile/page.tsx
  - frontend/src/app/(authenticated)/settings/page.tsx
  - backend/core/models/user_preferences.py
---

## Problem

The platform has light theme only, no avatar upload, no timezone management, and a basic profile page. User personalization is limited to thinking mode and response style preferences.

## What Exists (25%)

- Profile page with: AccountInfoCard, CustomInstructionsCard, LLMPreferencesCard, PasswordChangeCard
- User preferences model: `thinking_mode` (bool), `response_style` (concise|detailed|conversational)
- Settings pages for memory and channel linking
- Light theme only (fixed gray/blue palette)

## What's Needed

- **Dark theme + theme switcher** — CSS variables, Tailwind v4 theming, theme presets (light/dark/navy/custom)
- **Avatar upload** — upload, crop, storage (depends on #19 Storage Service for MinIO, or use local fallback for MVP)
- **Timezone management** — per-user timezone setting, system-wide default timezone admin setting
- **User bio/description** — bio field in profile
- **Contact preferences** — notification channel preferences
- **Profile visibility settings** — control over profile visibility to other users
- **Enhanced notification granularity** — per-event notification controls (not all-or-nothing)

## Solution

Follow specification at `docs/enhancement/topics/13-user-experience-enhancement/00-specification.md`.
