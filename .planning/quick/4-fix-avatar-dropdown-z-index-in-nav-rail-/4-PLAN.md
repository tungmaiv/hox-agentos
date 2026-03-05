---
phase: quick
plan: 4
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/components/nav-rail.tsx
autonomous: true
requirements: []
must_haves:
  truths:
    - "Avatar dropdown renders above all page content when opened"
    - "Dropdown is not clipped or obscured by any overlapping element"
  artifacts:
    - path: "frontend/src/components/nav-rail.tsx"
      provides: "NavRail with corrected z-index on nav element"
      contains: "z-50"
  key_links:
    - from: "frontend/src/components/nav-rail.tsx"
      to: "nav element stacking context"
      via: "z-50 class on <nav>"
      pattern: "z-50"
---

<objective>
Fix the avatar dropdown in NavRail being obscured by page content by raising the nav element's z-index from z-40 to z-50.

Purpose: The `<nav>` element at line 96 uses `z-40`, which creates a stacking context. The dropdown inside it already uses `z-50`, but that z-index is scoped within the nav's stacking context — meaning the dropdown can only stack above siblings inside the nav, not above other page elements with z-40 or higher. Raising the nav to `z-50` ensures the entire nav (and its dropdown child) stacks above all other page content.

Output: Single-line change in nav-rail.tsx.
</objective>

<execution_context>
@/home/tungmv/.claude/get-shit-done/workflows/execute-plan.md
@/home/tungmv/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@frontend/src/components/nav-rail.tsx
</context>

<tasks>

<task type="auto">
  <name>Task 1: Raise nav element z-index from z-40 to z-50</name>
  <files>frontend/src/components/nav-rail.tsx</files>
  <action>
    On line 96 of `frontend/src/components/nav-rail.tsx`, change the `z-40` class on the `<nav>` element to `z-50`.

    Before:
    ```tsx
    className="hidden md:flex flex-col fixed left-0 top-0 h-screen w-16 z-40"
    ```

    After:
    ```tsx
    className="hidden md:flex flex-col fixed left-0 top-0 h-screen w-16 z-50"
    ```

    Why: The `<nav>` element creates a CSS stacking context. The dropdown inside it (line 164) has `z-50`, but that only elevates it within the nav's stacking context — it cannot escape the nav's own z-level of z-40. Any sibling page element with z-40+ will render above the dropdown. Raising the nav to z-50 lets the entire nav stacking context sit above all z-40 elements on the page, so the dropdown (z-50 within nav) is visible above everything.

    Do not change the dropdown's `z-50` class at line 164 — it is correct and should remain.
  </action>
  <verify>
    <automated>cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit</automated>
  </verify>
  <done>
    - `frontend/src/components/nav-rail.tsx` line 96 has `z-50` on the nav element
    - TypeScript build (`pnpm exec tsc --noEmit`) passes with no errors
    - Dropdown at line 164 still has `z-50` (unchanged)
  </done>
</task>

</tasks>

<verification>
After the change:
1. `grep -n "z-40\|z-50" frontend/src/components/nav-rail.tsx` should show only `z-50` entries (no remaining `z-40`)
2. `pnpm exec tsc --noEmit` passes in `/home/tungmv/Projects/hox-agentos/frontend`
</verification>

<success_criteria>
Nav element uses `z-50` and the avatar dropdown is no longer obscured by page content. TypeScript check passes. No other classes modified.
</success_criteria>

<output>
After completion, create `.planning/quick/4-fix-avatar-dropdown-z-index-in-nav-rail-/4-SUMMARY.md`
</output>
