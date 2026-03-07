# Phase 20 Design: Skill Platform B — Discovery & Catalog

**Date:** 2026-03-07
**Phase:** 20 of 23 (v1.3)
**Depends on:** Phase 19 (spec-compliant schema: category, tags, source_url columns exist)
**Requirements:** SKCAT-01, SKCAT-02, SKCAT-03, SKCAT-04

---

## Goal

Users can search and filter the skill catalog relevant to their role. Admins can search all skills and tools, browse external registries with paginated results, and import skills via a one-click flow with full metadata preview before committing.

---

## Current State

- `GET /api/admin/skills` — filters: status, skill_type, version. No text search, no author, no sort.
- `GET /api/skills` — role-filtered, no search params at all.
- `GET /api/admin/tools` — filters: status, version. No name search, no handler_type filter.
- `GET /api/skill-repos/browse` — returns full list (no pagination); backend is `user_router` with `chat` permission despite being admin-only in UI (security gap).
- `POST /api/skill-repos/import` — same security gap: `user_router` / `chat`.
- `skill-store-browse.tsx` — has search bar + 2-step import dialog (confirm → security scan result). No pagination. No full metadata preview.

---

## Access Model

| Surface | Who | Visibility |
|---------|-----|-----------|
| `/skills` | All authenticated users | Active skills permitted for their roles |
| `/admin/skills` | Admin / IT-admin / Developer | All skills regardless of status |
| `/admin` tools tab | Admin / IT-admin / Developer | All tools |
| `/admin/skill-store` browse + import | Admin / IT-admin / Developer | External repos (admin-only) |

---

## Plan 20-01: FTS Migration + Backend Search APIs

### Migration 023

Add a `tsvector` generated column to `skill_definitions`:

```sql
ALTER TABLE skill_definitions
ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (
    to_tsvector('simple',
      name || ' ' ||
      coalesce(description, '') || ' ' ||
      coalesce(array_to_string(tags::text[], ' '), ''))
  ) STORED;

CREATE INDEX ix_skill_definitions_search_vector
  ON skill_definitions USING GIN (search_vector);
```

`'simple'` config: strips stop words without language-specific stemming. Correct for Vietnamese — no diacritic normalization needed at index time since pgvector `'simple'` handles it.

No migration needed for tools — tools use ILIKE (admin-only, smaller dataset).

### API Changes

**`GET /api/admin/skills`** — new query params:
- `q: str | None` — FTS via `search_vector @@ plainto_tsquery('simple', q)`
- `category: str | None` — exact match on `category` column
- `author: UUID | None` — filter by `created_by`
- `sort: str` — one of `name`, `created_at`, `updated_at` (default: `updated_at`)
- `order: str` — `asc` | `desc` (default: `desc`)

**`GET /api/skills`** — new query params:
- `q: str | None` — same FTS
- `category: str | None` — exact match
- `sort: str` — `name` | `created_at` | `updated_at` (default: `updated_at`)

Note: "sort by usage" dropped — no `usage_count` column exists and wiring execution tracking is out of scope for this phase.

**`GET /api/admin/tools`** — new query params:
- `q: str | None` — ILIKE on `name` and `description` (`%q%`)
- `handler_type: str | None` — exact match on `handler_type`

### Tests

- FTS returns correct results for English and Vietnamese queries
- Category filter, author filter, sort params all return correctly filtered/ordered results
- ILIKE tool search returns matching tools by name fragment
- handler_type filter returns only matching tools
- Empty `q` falls back to full list (no crash)

---

## Plan 20-02: Frontend Catalog UIs

Pure frontend work — wires new query params from Plan 01 into three existing pages.

### User `/skills` page

- Search bar (300ms debounce) — sends `?q=`
- Category chip filters — unique categories fetched from API response, send `?category=`
- Sort dropdown: Newest / Oldest / Name A-Z — sends `?sort=&order=`

### Admin `/admin/skills` tab

- Search bar (300ms debounce) — sends `?q=`
- Dropdowns: Category, Status, Sort
- Author filter: UUID input or name lookup (simple text input, sends `?author=`)

### Admin tools tab

- Search bar (300ms debounce) — sends `?q=`
- handler_type dropdown: all, mcp, openapi_proxy, builtin, sandbox

All three use existing component patterns (debounced input hook, query param state, refetch on change).

---

## Plan 20-03: External Registry Browse Hardening

### Security Fix

Move `GET /api/skill-repos/browse` and `POST /api/skill-repos/import` from `user_router` (chat permission) to `admin_router` (registry:manage permission).

Update `skill-store-browse.tsx` to call `/api/admin/skill-repos/browse` and `/api/admin/skill-repos/import`.

### Pagination

Add `page: int = 1` and `limit: int = 20` to the browse endpoint. Service slices the cached index and returns:

```json
{
  "items": [...],
  "total": 142,
  "page": 1,
  "limit": 20,
  "has_more": true
}
```

Frontend adds "Load more" button that appends next page to existing results.

### Skill Detail Preview

Expand the existing 2-step import dialog (confirm → security scan result) to show full metadata before the confirm step:

```
[Detail panel]
Name, version, description
Category | License | Compatibility
Tags (chips)
Source URL (link)
Allowed tools (if declared)
Repository: <name>

[Import button] → confirm → security scan result
```

No new backend endpoint needed — all metadata is already in `SkillBrowseItem` (may need to pass through additional fields from the cached index).

---

## Non-Goals (Deferred)

- Usage tracking (`usage_count` column) — separate phase
- User-facing external browse — admin-only by decision
- Autocomplete/typeahead on search — overkill at 100-user scale
- Saved search filters — overkill for MVP

---

## Gate Criteria (Phase 20 UAT)

1. Searching "calendar" on `/skills` returns only active skills matching that term, scoped to the user's roles
2. Admin searching on `/admin/skills` with `q`, `category`, `status`, and `sort` all work independently and combined
3. Admin tools tab search by name fragment and handler_type filter returns correct results
4. External registry browse shows paginated results (20/page) with "Load more"
5. Clicking a skill in browse shows full metadata (license, tags, category, source_url) before import dialog
6. `GET /api/skill-repos/browse` returns 403 for a user with only `chat` role (security fix confirmed)
