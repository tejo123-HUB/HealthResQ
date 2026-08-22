# HealthResQ UI/UX Decision Spec

## Purpose & process

This document is the output of a staged, persona-driven UI/UX interview covering every screen
in HealthResQ. For each screen: a targeted research pass grounded the interview in real
UX/accessibility/domain best practice (with sourcing confidence noted where it matters), a
hypothesis was stated, and concrete decisions were locked through an explicit, structured
confirmation with the product owner. It is a decision spec, not implementation — it is the
handoff document for a later design/build pass.

## Global principles (apply to every screen)

1. **Full functionality, always.** A screen's persona being "time-pressed" governs information
   hierarchy and interaction speed — never feature completeness. No screen should end up
   stripped-down or look basic because its persona is busy; every screen stays fully functional
   and polished/considered even outside a rushed moment.
2. **Glass/blur is the default premium visual language, with an automatic performance
   fallback.** Translucent/blur treatments are used by default for a premium feel, gated by a
   runtime performance-feedback loop that automatically drops to a flat/layered-token look when
   a device can't sustain it smoothly. Applies app-wide (originated at Login, generalized to all
   chrome and screens).
3. **Motion is respectful and accountable.** All animation honors `prefers-reduced-motion`; any
   auto-playing animation running longer than 5 seconds gets an explicit in-page pause/stop
   control (WCAG 2.2.2) — not just an OS-level reduced-motion guard.
4. **Severity color is sacred.** The 4-tier severity language (Normal/Watch/High/Critical) is
   reserved exclusively for genuine risk/urgency. It must never be reused for plain
   categorical/operational state (bed occupancy, pipeline stage, a structural privacy guarantee,
   etc.) — those get their own neutral palettes. Severity summaries order most-severe-first;
   non-risk states (e.g. "Normal") are visually demoted to muted/plain treatment, never a
   full-strength badge.
5. **Automatic region-based translation/localization is a standing app-wide principle** —
   not limited to any single screen (originated at the Recommendations flow, generalized to the
   whole app).
6. **The human always decides.** The AI agent drafts, explains, and proposes; a human explicitly
   approves before anything executes — this constrains every AI-surface design decision in this
   spec (no confidence scores implying model judgment, no silent auto-execution).

## Screens

### 1. Login / Entry
**Source:** `frontend/app/login/page.tsx`, `frontend/app/page.tsx`
**Persona:** Any role, first touch — often a shared/low-power device inside a health facility;
needs instant trust and a fast way in, but it must still look premium.
**Key research finding:** the screen hardcodes a demo password and lists all demo accounts in a
visible footer — the single loudest anti-trust signal on the screen.

Decisions:
- Demo accounts hidden behind a "Demo accounts" disclosure toggle (not always-visible, not removed).
- Visual language: glass/blur aesthetic (translucent card, backdrop blur, aurora-style gradient),
  governed by global principle #2's performance fallback.
- Password field gets a show/hide toggle and generic "invalid credentials" messaging (never
  reveals which field was wrong).
- Entrance motion stays as-is (breathing logo + staggered fade/scale-in), with
  `prefers-reduced-motion` support added.

### 2. Shared chrome (Nav bar, AgentPane, encrypted Inbox)
**Source:** `components/Nav.tsx`, `components/AgentPane.tsx`, `components/mailbox/InboxPanel.tsx`
**Persona:** Cross-cutting — must stay unobtrusive to whichever time-pressed persona is
currently on screen.
**Key research finding:** persistent AI side panels (GitHub Copilot Chat, Microsoft Copilot)
converge on fixed-width, always-visible, summary-first placement.

Decisions:
- AgentPane: fixed-width, summary-first (AI suggestion collapsed, chat as expand), collapsible
  to an icon rail — never fully hidden.
- Inbox unread/urgent state uses the existing SeverityBadge color system rather than a new
  visual language.
- Nav bar stays strictly identity + session controls (logo, scope, theme toggle, sign-out) — no
  page links, no search/switcher added speculatively.
- Visual style: glass/blur app-wide per global principle #2 (the login-only vs. everywhere
  question was resolved in favor of everywhere, with the performance-adaptive fallback covering
  the always-on-chrome cost concern).

### 3. Facility Home (PHC/SHC "Overview" tab)
**Source:** `frontend/app/phc/page.tsx`, `frontend/app/shc/page.tsx` (`FacilityHome`)
**Persona:** Time-pressed PHC/SHC operator logging data between patients — wants at-a-glance
status, minimal taps.
**Key research finding:** the low-stock card (the only alert-bearing metric) is placed last in
the grid, and uses one flat `<100 units` threshold for every product regardless of type — a
known alarm-fatigue driver.

Decisions:
- Low-stock card reorders to lead position by default.
- Stock severity coloring switches from a flat threshold to a relative/days-of-supply signal per
  product.
- All 4 severity tiers stay visually distinct (no collapsing Watch into Normal/High).
- Sparklines reserved for 1-2 decision-relevant cards; any hover/elevation polish is paired with
  a touch-safe, always-visible equivalent.
- **Lightweight pin/reorder customize mode**: operators can personalize card order and which
  cards show a sparkline; the defaults above apply for anyone who never customizes.

### 4. Hospital Management tab
**Source:** `components/hms/*` (WardList, BedGrid, OTScheduler, ReferralTracker), inside `/shc`
**Persona:** Time-pressed hospital admin staff — fast state changes (admit/discharge/schedule),
not analysis.
**Key research finding:** BedGrid reuses the app's severity/alarm color tokens for plain
occupancy state, so an occupied bed always visually reads as "critical alarm."

Decisions:
- BedGrid occupancy gets its own neutral categorical palette, fully decoupled from
  severity/urgency colors (global principle #4).
- Confirm sheet retained for **both** admit and discharge (safety prioritized over tap-speed here).
- OT scheduling prevents conflicts inline via tap-first quick-pick slots (grayed-out conflicts) —
  no more post-submit conflict errors.
- ReferralTracker shows status via a compact inline 3-segment indicator per row, not a full
  stepper component.

### 5. Warehouse workspace
**Source:** `frontend/app/warehouse/page.tsx`
**Persona:** Time-pressed warehouse operator tracking the dispatch pipeline — needs status at a
glance, often on a connectivity-constrained device.
**Key research finding:** the tracker is labeled 3 stages (ACKNOWLEDGE→PREPARE→DISPATCH) but the
real state machine has 5 stages plus a BLOCKED branch; pipeline stages also repeat the
severity-color misuse found in Hospital Management.

Decisions:
- Tracker keeps its simple 3-stage label at a glance; tapping an order reveals the true 5-stage +
  Blocked sub-state in a detail view.
- Pipeline stage colors move to a neutral palette; severity red/orange reserved strictly for
  Blocked and overdue orders (global principle #4).
- "Advance" stays an instant single tap; "Blocked" (the exception/harder-to-reverse path) gets a
  confirm step.
- Stage advances become optimistic UI updates with an offline queue and a sync badge, addressing
  the connectivity-constrained persona.

### 6. Authority Dashboard — Overview tab
**Source:** `components/DashboardScreen.tsx` (Overview), rendered at `/district`, `/state`, `/national`
**Persona:** Time-pressed district/state/national official skimming between meetings for what
needs attention.
**Key research finding:** the severity breakdown lists Normal→Watch→High→Critical — least urgent
first, burying the thing the official most needs to see.

Decisions:
- Severity list reorders to Critical→Normal (most severe first).
- "Normal" demoted to a plain/muted count; saturated severity color stays exclusive to
  Watch/High/Critical.
- Each severity row gets a thin proportional (length-encoded) bar for faster preattentive scanning.
- The Total-deficit stat card's severity-colored "warning" tone is confirmed as a legitimate risk
  signal (unlike bed occupancy/pipeline stage) and kept as-is.

### 7. Authority Dashboard — Risk map tab
**Source:** `components/RiskMap.tsx`
**Persona:** Same official, scanning geography for hotspots/outliers in seconds.
**Key research finding:** Watch and High currently render as the identical color on the map,
silently collapsing the 4-tier system to 3, with color as the marker's only channel (no adjacent
text) — a colorblind-accessibility failure as well as a bug.

Decisions:
- Each severity tier gets a genuinely distinct hue plus a redundant shape/icon on markers
  (matches the color+icon redundancy principle already used by `SeverityBadge`).
- A choropleth region overlay colors each administrative region by an aggregated/extrapolated
  severity score across its facilities, shown under individual facility markers; markers reveal
  full detail as the official zooms in.
- Pulsing constrained to a rarity budget (only the single highest-severity outlier per
  cluster/viewport pulses) plus an explicit pause-motion control (closes a real WCAG 2.2.2 gap).
- Basemap moves off raw OpenStreetMap raster tiles (a policy violation) to a compliant,
  desaturated vector basemap, sourced from free/open providers (e.g. OpenFreeMap, Protomaps)
  where available; raw OSM tiles remain only as a last-resort fallback.

### 8. Authority Dashboard — Explorer tab
**Source:** `components/ResourceExplorer.tsx`
**Persona:** Same official, in deliberate "occasional drill-down" mode after spotting something
via Overview/Risk map.
**Key research finding:** BI drill-through best practice says a selection should carry forward as
a filter, not reset, when moving from summary to detail.

Decisions:
- Selecting a facility/bar in the Overview chart carries over as a clearable filter chip into
  Full Data — the toggle feels like zooming, not switching screens.
- Overview chart caps at ~8 worst facilities with a muted deficit-threshold reference line;
  severity color applied only to bars that actually cross into Watch/High/Critical.
- Full Data table gets the full big-table treatment: sticky header/column, right-aligned numeric
  columns, per-column filter/sort, virtual scroll.
- Forecast uncertainty shown as an on-demand band (hover/expand) with a plain-language label
  ("model less certain"), never a raw confidence-interval number — keeps the classical-statistics
  framing honest without overwhelming a non-technical reader.

### 9. Authority Dashboard — Federation tab (National only)
**Source:** `components/FederationPanel.tsx`
**Persona:** National policymaker comparing BRICS partners — strategic, occasional,
briefing/report-oriented use; still held to full-functionality/full-polish standards.
**Key research finding:** the "0 raw records shared" privacy-guarantee card misuses green
severity color and a pop-in animation on a value that never changes.

Decisions:
- Privacy-guarantee card restyled to a neutral color with a static lock/shield icon — no more
  severity-color or animation misuse.
- Countries sorted **descending by a chosen metric** (a deliberate leaderboard-style comparison,
  chosen over the alphabetical/peer-group alternatives the research favored).
- Demand-trend chart gains a time axis via the existing `latestRound` field before any
  grouped-bar-vs-small-multiples layout decision is made.
- A dedicated **presentation/export mode** is added: enlarged fonts, hidden app chrome, clean
  exportable image — for briefing/report use.

### 10. Recommendations queue + decision detail
**Source:** `frontend/app/recommendations/page.tsx`, `frontend/app/recommendations/[id]/page.tsx`
**Persona:** Time-pressed official approving/rejecting/escalating — a real accountable decision,
not a rubber-stamp.
**Key research finding:** a numeric "AI confidence" badge would itself violate the product's
hard rule that the LLM never decides, by implying the model is judging.

Decisions:
- AI output is presented as an easily-understood **plan** derived from the underlying numbers
  (plain language, not a confidence score or jargon-heavy evidence dump), collapsed by default
  with expand-on-demand detail.
- Outdated recommendations use a non-blocking, inline "Recalculate" CTA (GitHub stale-review
  pattern) — the rest of the queue stays fully usable.
- **Escalation is redefined as whole-action escalation**: no quantity-input bump; escalating
  routes the entire recommendation/action to the next authority tier. No typed justification is
  required, but every escalation is automatically logged for audit purposes.
- Batch actions are supported in the queue, **including batch-approve** (a deliberate choice
  accepting the tension with strict one-at-a-time review, in exchange for queue throughput).

### 11. Compose action (agentic, chat-driven composer)
**Source:** `frontend/app/orders/new/page.tsx` — explicitly redefined away from a form
**Persona:** Time-pressed official who wants to converse with the AI agent rather than fill
fields, but must end with full confidence in exactly what will be dispatched.
**Key research finding:** human-in-the-loop agent guidance (Microsoft AG-UI, OpenAI Agents SDK)
recommends approving sensitive actions individually rather than in one batch — a direct tension
with a single Go/Approve-everything flow, resolved below rather than silently picked one way.

Decisions:
- **Split-pane layout**: a persistent "what will actually be dispatched" list on one side, the
  conversational thread on the other — the current truth is never buried in chat history.
- The agent opens by proactively presenting a list of probable/candidate actions as distinct,
  reviewable cards; conversation can edit existing candidates or add new ones.
- **Two approval paths, both available**: a per-item "Go" on each card (the default, most
  careful path) and a bulk "Go all" for the whole list — the bulk path requires an explicit
  warning + liability-acknowledgment clause before proceeding, and is logged with extra audit
  detail, since it skips individual per-card review.
- Each card is both directly editable (inline fields, collapsed by default, expandable) and
  editable via chat ("change quantity to X") — full field-level control survives without a
  separate form screen.
- New/updated cards get a full typing-indicator + streamed explanation before the card resolves —
  the richest entrance treatment in the app, matching this screen's more conversational,
  considered pace.
