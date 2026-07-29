# Outpost — Design System

A visual spec for a data-dense B2B outreach command center. Direction: clean, modern, dense, trustworthy — restraint over decoration, closer to Linear / Vercel than a consumer app. Tokens ship in **light** and **dark**; dark is a first-class peer for long sessions.

Live reference: `Outpost Design System.dc.html`.

---

## 1. Color tokens

Format: `token` — usage — `light` / `dark`. In code these are CSS custom properties (`--token`), swapped by a `data-theme="dark"` attribute on the root.

### Neutrals & surfaces
| Token | Usage | Light | Dark |
|---|---|---|---|
| `bg` | App background | `#FAFAFA` | `#09090B` |
| `bg-subtle` | Sunken areas, table headers | `#F4F4F5` | `#131316` |
| `surface` | Cards, panels, rows | `#FFFFFF` | `#18181B` |
| `surface-hover` | Row / item hover | `#F7F7F8` | `#232327` |
| `border` | Default hairline borders | `#E4E4E7` | `#27272A` |
| `border-strong` | Inputs, dividers, emphasis | `#D4D4D8` | `#3F3F46` |

### Text
| Token | Usage | Light | Dark |
|---|---|---|---|
| `text` | Primary text, headings | `#18181B` | `#FAFAFA` |
| `text-2` | Secondary, labels, meta | `#52525B` | `#A1A1AA` |
| `text-3` | Muted, placeholders | `#A1A1AA` | `#71717A` |

### Accent (primary action) — indigo
| Token | Usage | Light | Dark |
|---|---|---|---|
| `accent` | Primary buttons, active nav, links | `#4F46E5` | `#6366F1` |
| `accent-hover` | Hover / pressed | `#4338CA` | `#818CF8` |
| `accent-fg` | Foreground on accent | `#FFFFFF` | `#FFFFFF` |
| `accent-subtle` | Selected background, tints | `#EEF2FF` | `#1E1B4B` |
| `accent-border` | Focused / selected border | `#C7D2FE` | `#3730A3` |
| `ring` | Focus ring (3px glow) | `rgba(79,70,229,.35)` | `rgba(99,102,241,.4)` |

_Optional accent swaps (same roles): **blue** `#2563EB`/`#3B82F6`, **violet** `#7C3AED`/`#8B5CF6`._

### Semantic
| Token | Usage | Light | Dark |
|---|---|---|---|
| `success` | Approved, healthy | `#16A34A` | `#22C55E` |
| `success-subtle` | Badge / pill background | `#DCFCE7` | `#14261B` |
| `warning` | Needs attention | `#D97706` | `#F59E0B` |
| `warning-subtle` | Badge / pill background | `#FEF3C7` | `#2A2110` |
| `error` | Rejected, failed, destructive | `#DC2626` | `#EF4444` |
| `error-subtle` | Badge / pill background | `#FEE2E2` | `#2A1516` |
| `info` | Neutral info, auto-drafted | `#2563EB` | `#3B82F6` |
| `info-subtle` | Badge / pill background | `#DBEAFE` | `#16233A` |

### Pipeline stages (contacted → replied → live)
| Token | Usage | Light | Dark | Subtle (light / dark) |
|---|---|---|---|---|
| `pl-queued` | Discovered, not yet contacted | `#64748B` | `#94A3B8` | `#F1F5F9` / `#1E2530` |
| `pl-contacted` | Outreach sent | `#2563EB` | `#60A5FA` | `#DBEAFE` / `#16233A` |
| `pl-replied` | Prospect responded | `#7C3AED` | `#A78BFA` | `#EDE9FE` / `#241C3A` |
| `pl-live` | Deal / collab active | `#16A34A` | `#4ADE80` | `#DCFCE7` / `#14261B` |
| `pl-declined` | Passed / lost | `#E11D48` | `#FB7185` | `#FFE4E6` / `#2E1519` |

Pipeline hues share saturated foreground + a low-chroma tinted background; pills use foreground text on the subtle background plus a small dot.

---

## 2. Typography

**Family (sans):** native system UI stack — `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, Roboto, sans-serif`. Zero load, native rendering, ideal for density. Swap for Geist or IBM Plex Sans if a hosted brand face is required.

**Family (mono):** `ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas, monospace` — fit scores, IDs, reach counts, timestamps (tabular alignment).

**Weights:** 400 / 500 / 600 only.

| Level | Size | Weight | Line-height | Usage |
|---|---|---|---|---|
| Page title | 24px | 600 | 32px | Screen H1, one per view |
| Section | 20px | 600 | 28px | Panel & card-group headings |
| Subsection | 16px | 600 | 24px | Card titles, dialog headers |
| Body | 14px | 400 | 20px | Default UI text, form values |
| Table | 13px | 400 | 18px | Dense table cells & lists |
| Label | 12px | 500 | 16px | Field labels, column headers (letter-spacing .04em, often uppercase) |
| Micro | 11px | 500 | 14px | Badges, timestamps, counts |

Headings use `letter-spacing: -0.01em`. Never below 11px.

---

## 3. Spacing & layout

**Base unit: 4px.** Compose everything from the scale.

| px | ×base | Usage |
|---|---|---|
| 4 | 1× | Icon/text gap, chip padding |
| 8 | 2× | Compact gaps, badge padding |
| 12 | 3× | Control padding, list gaps |
| 16 | 4× | Card padding (compact), field gaps |
| 20 | 5× | Card padding (default) |
| 24 | 6× | Section inner gaps |
| 32 | 8× | Page gutters, panel padding |
| 40 | 10× | Between subsections |
| 48 | 12× | Between major blocks |
| 64 | 16× | Between top-level sections |

**Radius:** `4px` badges/pills · `6px` controls (buttons, inputs) · `8px` cards/panels · `9999px` avatars & status pills.

**Borders:** 1px, `border` default, `border-strong` on inputs. Elevation comes from borders first; shadows are minimal — `0 1px 2px rgba(24,24,27,.04), 0 1px 3px rgba(24,24,27,.06)` (light), heavier alpha in dark.

**Table density:** comfortable row = 40px (10px vertical padding); compact = 32px (6px) for triage. Card padding 16px compact / 20px default. Side rail fixed at 248px. Content gutters 32px.

---

## 4. Components

**Buttons** — height 34px default / 28px small, radius 6px, font 13px (600 primary, 500 secondary).
- Primary: `accent` bg + `accent-fg`; hover `accent-hover`.
- Secondary: `surface` bg + 1px `border-strong` + `text`; hover `surface-hover`.
- Ghost: transparent + `text-2`; hover `surface-hover`, text → `text`.
- Destructive: `error` bg + white; hover brightness .93.
- Disabled: opacity .45, `not-allowed`.

**Status badges / pipeline pills** — radius 9999px, 11px/600, `3px 10px` padding, 6px dot in `currentColor`. Foreground = semantic/pipeline token, background = its `-subtle` token.

**Inputs** — height 34px, radius 6px, 1px `border-strong`, `surface` bg, 13px text. Focus: border → `accent` + `0 0 0 3px ring`. Error: border → `error`, helper text `error`. Disabled: `bg-subtle` + `text-3`. Placeholder `text-3`. Textarea min-height 74px, vertical resize.

**Table** — header row `bg-subtle`, labels 11px/600 `text-3` uppercase (.05em). Cells 13px, `row-pad` vertical. Rows separated by 1px `border`; hover `surface-hover`. Numeric columns (fit, reach) right-aligned in mono. Fit score coloring: ≥85 `success`, 70–84 `text`, <70 `text-3`.

**Side navigation** — fixed 248px `surface` rail, 12px padding. Items 34px tall, radius 6px, 13px/500 `text-2` with 16px icon; hover `surface-hover` → `text`. Active item: `accent-subtle` bg + `accent` text/icon, 600. Counts are mono pills (`bg-subtle`/`text-3`); the active/backlog count inverts to solid `accent`.
