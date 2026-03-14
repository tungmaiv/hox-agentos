# User Experience Enhancement (UI Theme + User Profile)

**Status:** ✅ Design Complete  
**Priority:** Medium  
**Target:** v1.4  
**Estimated Effort:** 1 Phase (6 weeks)  
**Last Updated:** 2026-03-16

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Architecture Overview](#architecture-overview)
4. [Theme System](#theme-system)
5. [User Profile System](#user-profile-system)
6. [Timezone Management](#timezone-management)
7. [Implementation Phases](#implementation-phases)
8. [Success Criteria](#success-criteria)
9. [Risks and Mitigations](#risks-and-mitigations)
10. [Related Documents](#related-documents)

---

## Executive Summary

This enhancement transforms AgentOS from a functional but utilitarian interface into a polished, personalized user experience. It combines a comprehensive **UI Theme System** with a **Full User Profile** management system, plus **dual-level timezone management** (system-wide and per-user).

### Key Components

```
┌─────────────────────────────────────────────────────────────────┐
│              USER EXPERIENCE ENHANCEMENT SYSTEM                  │
├──────────────────────────────┬──────────────────────────────────┤
│     UI THEME SYSTEM          │       FULL USER PROFILE          │
├──────────────────────────────┼──────────────────────────────────┤
│ • 3 Built-in Themes          │ • Avatar Upload (MinIO)          │
│   - Light                    │ • Display Name                   │
│   - Dark                     │ • Bio/Description                │
│   - Navy Blue                │ • Contact Preferences            │
│ • Color Customization        │ • Notification Settings          │
│   - 6 Curated Presets        │ • User Preferences               │
│   - Custom Hex Input         │ • Profile Visibility             │
│ • System Preference Detection│ • User Timezone                  │
│ • Smooth Transitions         │                                  │
├──────────────────────────────┼──────────────────────────────────┤
│              SYSTEM-WIDE SETTINGS (Admin)                       │
├──────────────────────────────┴──────────────────────────────────┤
│ • Default Theme                                                  │
│ • Default Timezone                                              │
│ • Available Themes (enable/disable)                             │
│ • Color Palette Restrictions                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Technical Highlights

- **CSS Variables Architecture**: Tailwind v4 native theming with instant switching
- **MinIO Storage**: Scalable S3-compatible object storage for avatars
- **Dual Timezone**: System timezone for operations, user timezone for display
- **Zero Flash**: Theme applied before React hydration

---

## Problem Statement

### Current State (As-Is)

| Aspect | Current Reality | Pain Point |
|--------|----------------|------------|
| **Theme** | Light mode only | No dark mode for night use; no personalization |
| **Colors** | Fixed blue palette | No brand alignment or personal preference |
| **Avatar** | Generic initials only | No personal identity; harder to recognize users |
| **Profile** | Basic info only | No bio, no customization, feels impersonal |
| **Timezone** | UTC only | Users see wrong times; scheduling confusion |
| **Notifications** | All or nothing | Cannot customize by channel or priority |

### Target State (To-Be)

| Aspect | Target Experience | Benefit |
|--------|------------------|---------|
| **Theme** | 3 built-in themes + custom colors | Comfortable viewing, personalization |
| **Avatar** | Photo upload with crop | Personal identity, better recognition |
| **Profile** | Rich profile with bio | Community feel, professional presentation |
| **Timezone** | Automatic + manual selection | Correct times for all users globally |
| **Notifications** | Granular control | Reduced noise, relevant alerts |

---

## Architecture Overview

### CSS Variables Strategy

Using Tailwind CSS v4's native CSS variable support for zero-JavaScript-overhead theming:

```css
/* globals.css - Theme Definitions */
:root,
.light {
  --background: #ffffff;
  --foreground: #171717;
  --card: #ffffff;
  --card-foreground: #171717;
  --primary: #0066cc;
  --primary-foreground: #ffffff;
  --secondary: #f5f5f5;
  --secondary-foreground: #171717;
  --accent: #f97316;
  --accent-foreground: #ffffff;
  --border: #e5e5e5;
  --input: #e5e5e5;
  --ring: #0066cc;
  --radius: 0.5rem;
  --destructive: #ef4444;
  --success: #22c55e;
  --warning: #f59e0b;
}

.dark {
  --background: #0a0a0a;
  --foreground: #fafafa;
  --card: #171717;
  --card-foreground: #fafafa;
  --primary: #3b82f6;
  --secondary: #262626;
  --secondary-foreground: #fafafa;
  --accent: #f97316;
  --border: #262626;
  --input: #262626;
  --ring: #3b82f6;
}

.navyblue {
  --background: #0f172a;
  --foreground: #f8fafc;
  --card: #1e293b;
  --card-foreground: #f8fafc;
  --primary: #60a5fa;
  --secondary: #1e293b;
  --secondary-foreground: #f8fafc;
  --accent: #38bdf8;
  --border: #334155;
  --input: #334155;
  --ring: #60a5fa;
}
```

### Data Persistence

| Data | Storage | Scope | Rationale |
|------|---------|-------|-----------|
| **System Timezone** | PostgreSQL | Global | Admin-controlled default |
| **User Timezone** | PostgreSQL | Per-user | User preference |
| **Theme Selection** | localStorage + Database | Per-user | Instant load, cross-device |
| **Custom Colors** | Database | Per-user | Persist preferences |
| **Avatar** | MinIO (S3-compatible) | Per-user | Scalable file storage |
| **Profile Fields** | PostgreSQL | Per-user | Structured data |
| **Notification Settings** | PostgreSQL | Per-user | Backend routing |

### Theme Application Flow

```
User Selects Theme
       │
       ▼
┌──────────────┐
│ localStorage │ ──► Instant UI update (no flash)
└──────────────┘
       │
       ▼
┌──────────────┐
│   Backend    │ ──► Persist to database (async)
└──────────────┘
       │
       ▼
┌──────────────┐
│  PostgreSQL  │ ──► User settings table
└──────────────┘
```

### Avatar Storage Architecture

```
User selects image
       │
       ▼
┌──────────────┐
│ File Upload  │ ──► Validate (JPG/PNG, max 5MB)
└──────────────┘
       │
       ▼
┌──────────────┐
│ Crop/Resize  │ ──► Fixed 1:1 ratio, min 200x200px
└──────────────┘
       │
       ▼
┌──────────────┐
│    MinIO     │ ──► Store in /avatars/{user_id}/{filename}
└──────────────┘
       │
       ▼
┌──────────────┐
│   Backend    │ ──► Save URL to user_settings.avatar_url
└──────────────┘
```

---

## Theme System

### 3 Built-in Themes

| Theme | Background | Primary | Use Case |
|-------|------------|---------|----------|
| **Light** | `#ffffff` | `#0066cc` | Default, daytime, office use |
| **Dark** | `#0a0a0a` | `#3b82f6` | Nighttime, reduced eye strain |
| **Navy Blue** | `#0f172a` | `#60a5fa` | Professional, focused work |

### Color Customization

**Curated Color Presets:**

```typescript
const colorPresets = [
  { name: "Ocean Blue", primary: "#0066cc", secondary: "#3b82f6", accent: "#06b6d4" },
  { name: "Forest Green", primary: "#16a34a", secondary: "#22c55e", accent: "#84cc16" },
  { name: "Royal Purple", primary: "#7c3aed", secondary: "#8b5cf6", accent: "#d946ef" },
  { name: "Sunset Orange", primary: "#ea580c", secondary: "#f97316", accent: "#fbbf24" },
  { name: "Ruby Red", primary: "#dc2626", secondary: "#ef4444", accent: "#fb7185" },
  { name: "Teal Wave", primary: "#0d9488", secondary: "#14b8a6", accent: "#2dd4bf" },
];
```

**Custom Hex Input:**
- Real-time preview
- WCAG contrast validation
- Reset to default option
- Storage as CSS variables

### Theme Components

**ThemeSelector Component:**
- Visual preview cards
- Live preview on hover
- System preference checkbox
- Selected state indicator

**ColorCustomizer Component:**
- Preset dropdown
- Custom color toggle
- Color pickers (Primary, Secondary, Accent)
- Contrast ratio indicator

### Smooth Transitions

```css
/* Apply to all color transitions */
* {
  transition: background-color 0.3s ease,
              color 0.3s ease,
              border-color 0.3s ease,
              box-shadow 0.3s ease;
}
```

---

## User Profile System

### Profile Page Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER PROFILE PAGE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  HEADER SECTION                                             ││
│  │  ┌─────────┐  Display Name (editable)                      ││
│  │  │         │  @username (from Keycloak)                    ││
│  │  │ Avatar  │  Bio/Description (textarea)                   ││
│  │  │         │                                               ││
│  └─────────────┴───────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  TAB NAVIGATION                                             ││
│  │  [Profile] [Preferences] [Notifications] [Security]         ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              ▼                                   │
│  TAB CONTENT (see below)                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Profile Tab

- **Contact Info**: Email, phone (if provided)
- **Department/Role**: Organization info
- **Profile Visibility**: Public / Organization / Private
- **Member Since**: Account creation date

### Preferences Tab

- **Theme Selection**: Light / Dark / Navy Blue
- **Color Customization**: Presets + custom hex
- **Language**: (if i18n implemented)
- **Timezone**: Searchable dropdown with major cities
- **Date Format**: MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD

### Notifications Tab

**Email Notifications:**
- Weekly digest
- Workflow failures
- Security alerts
- Marketing updates

**In-App Notifications:**
- New features
- Mentions in chat
- Workflow completions

**Channel Notifications:**
- Telegram enable/disable
- WhatsApp enable/disable
- Per-channel workflow alerts
- Per-channel security alerts

### Security Tab

- **Password Change**: (if local auth enabled)
- **Two-Factor Auth**: (if implemented)
- **Active Sessions**: View and revoke
- **Login History**: Recent activity

### Avatar Specifications

- **Formats**: JPG, PNG
- **Max Size**: 5MB
- **Sizes Generated**: 40x40px (nav), 120x120px (profile), 400x400px (full)
- **Aspect Ratio**: 1:1 (square, enforced via cropper)
- **Storage**: MinIO bucket `agentos-avatars`
- **URL Pattern**: `/avatars/{user_id}/{size}/{filename}`

### Profile Visibility Levels

| Level | Visible To | Use Case |
|-------|------------|----------|
| **Public** | Everyone in org | Team leads, public figures |
| **Organization** | All authenticated users | Standard employee |
| **Private** | Self + admins | Sensitive roles, privacy |

---

## Timezone Management

### Two-Level System

```
┌─────────────────────────────────────────┐
│         SYSTEM-WIDE TIMEZONE            │
│     (Admin Console > Settings)          │
│                                         │
│  Default: UTC                           │
│  Used for:                              │
│  • System logs                          │
│  • Scheduled jobs (Celery)              │
│  • Default for new users                │
│  • Analytics timestamps                 │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│          USER TIMEZONE                  │
│      (User Profile > Settings)          │
│                                         │
│  Default: System timezone               │
│  Used for:                              │
│  • Display times in UI                  │
│  • Converting UTC → Local               │
│  • Notification timing                  │
│  • "Good morning" greetings             │
└─────────────────────────────────────────┘
```

### Time Display Strategy

```typescript
// Backend stores everything in UTC
const createdAt = "2026-03-16T10:30:00Z"; // UTC

// Frontend converts to user's timezone
import { formatInTimeZone } from 'date-fns-tz';

const displayTime = formatInTimeZone(
  createdAt, 
  userTimezone, // e.g., "Asia/Ho_Chi_Minh"
  "MMM d, yyyy h:mm a"
);
// Result: "Mar 16, 2026 5:30 PM"
```

### Timezone Selector

- Searchable dropdown
- Major cities + UTC offset
- Grouped by region
- Detect from browser option

---

## Implementation Phases

### Phase 1: Foundation & Backend (Week 1)

**Database:**
```sql
-- User settings table
CREATE TABLE user_settings (
    user_id UUID PRIMARY KEY,
    theme VARCHAR(20) DEFAULT 'light',
    custom_colors JSONB,
    timezone VARCHAR(50) DEFAULT 'UTC',
    language VARCHAR(10) DEFAULT 'en',
    date_format VARCHAR(20) DEFAULT 'MM/DD/YYYY',
    display_name VARCHAR(100),
    bio TEXT,
    avatar_url VARCHAR(500),
    profile_visibility VARCHAR(20) DEFAULT 'organization',
    notification_settings JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Platform settings table (admin)
CREATE TABLE platform_settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value JSONB,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**MinIO Setup:**
- Add to docker-compose.yml
- Create `agentos-avatars` bucket
- Configure nginx reverse proxy

**API Endpoints:**
- `POST /api/users/avatar` - Upload avatar
- `GET /api/users/settings` - Get user settings
- `PUT /api/users/settings` - Update user settings
- `GET /api/platform/settings` - Get platform settings (admin)
- `PUT /api/platform/settings` - Update platform settings (admin)

**Deliverables:**
- Database migrations
- MinIO running
- Settings API functional

---

### Phase 2: Theme System (Week 2)

**CSS:**
- Update `globals.css` with 3 theme definitions
- Add transition styles

**Components:**
- `ThemeProvider` context
- `ThemeSelector` component
- `ColorCustomizer` component

**Integration:**
- Load theme on login
- Sync theme to backend
- Apply theme class to `<html>`

**Deliverables:**
- All 3 themes working
- Theme selector UI
- Color customization functional

---

### Phase 3: Avatar & Profile Header (Week 3)

**Components:**
- `AvatarUploader` with crop/resize
- `ProfileHeader` with avatar, name, bio
- Avatar in user menu
- Avatar in navigation rail

**Backend:**
- Image validation
- Multiple size generation
- MinIO upload

**Deliverables:**
- Avatar upload working
- Profile header complete
- Avatar visible throughout UI

---

### Phase 4: Profile Tabs (Week 4)

**Tabs:**
- **Profile**: Contact info, visibility
- **Preferences**: Theme, timezone, date format
- **Notifications**: Email, in-app, channels
- **Security**: Password, sessions

**Backend:**
- Update settings endpoints
- Notification routing
- Session management

**Deliverables:**
- All 4 tabs functional
- Settings save correctly
- Notifications respect preferences

---

### Phase 5: Admin System Settings (Week 5)

**Admin Console:**
- System settings page
- Default theme selector
- Default timezone selector
- Available themes toggle

**Integration:**
- New users inherit defaults
- Admin overrides

**Deliverables:**
- Admin can configure system defaults
- New users get system settings

---

### Phase 6: Polish & Testing (Week 6)

**Testing:**
- Timezone conversion across pages
- Theme transition smoothness
- Avatar edge cases
- Mobile responsiveness
- Accessibility (contrast ratios)
- Cross-browser testing

**Documentation:**
- User guide
- Admin guide
- API documentation

**Deliverables:**
- Production-ready code
- Documentation complete

---

## Success Criteria

### Theme System
- [ ] 3 built-in themes work (Light, Dark, Navy Blue)
- [ ] Theme switches instantly without page flash
- [ ] System preference detection works
- [ ] 6 curated color presets available
- [ ] Custom hex color input works with validation
- [ ] Theme persists across browser sessions
- [ ] Smooth CSS transitions between themes
- [ ] All components respect theme colors

### User Profile
- [ ] Avatar upload with crop/resize works
- [ ] Multiple avatar sizes generated (40px, 120px, 400px)
- [ ] Display name editable and persisted
- [ ] Bio/description field with character limit (500)
- [ ] Profile visibility settings work
- [ ] All 4 tabs functional (Profile, Preferences, Notifications, Security)
- [ ] Profile page accessible from user menu

### Timezone System
- [ ] System-wide timezone configurable by admin
- [ ] User timezone selectable with search
- [ ] All timestamps display in user's timezone
- [ ] Scheduled jobs respect system timezone
- [ ] Timezone conversion works correctly for all timezones

### Notification Settings
- [ ] Email notification toggles work
- [ ] In-app notification toggles work
- [ ] Channel notification settings (Telegram/WhatsApp) work
- [ ] Settings actually affect notification delivery

### Technical
- [ ] MinIO storage for avatars operational
- [ ] Settings API < 200ms response time
- [ ] Avatar upload < 3 seconds for 5MB file
- [ ] Mobile responsive (all features work on tablet)
- [ ] WCAG 2.1 AA contrast ratios met

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Theme flash on load** | Medium | Medium | Apply theme in `<head>` before render; use `suppressHydrationWarning` |
| **MinIO setup complexity** | Medium | Medium | Clear documentation; docker-compose pre-configured |
| **Timezone conversion bugs** | Medium | High | Use `date-fns-tz` library; comprehensive test cases |
| **Avatar storage quota** | Low | Medium | 5MB limit; periodic cleanup job |
| **Color contrast issues** | Medium | Medium | Validate WCAG ratios; warning for low contrast |
| **Browser compatibility** | Low | Medium | Test on Chrome, Firefox, Safari |
| **Migration from existing users** | Medium | Low | Default to Light theme; gradual rollout |

---

## Related Documents

- [Brainstorming Tracking](../BRAINSTORMING-TRACKING.md) - Project context and status
- [AgentOS Dashboard & Mission Control](../agentos-dashboard-mission-control/00-specification.md) - Consistent theming
- [Analytics & Observability Dashboard](../analytics-observability-dashboard/00-specification.md) - Timezone integration
- [Scheduler Engine & UI](../scheduler-engine-ui/00-specification.md) - Timezone for scheduling

---

**Document Owner:** Architecture Team  
**Reviewers:** Backend Team, Frontend Team, DevOps Team  
**Approved:** Pending Implementation Review
