# Locale content

`en/` is the source of truth — every other locale directory mirrors its namespace files
(`common.json`, `nav.json`, `login.json`, `dashboard.json`, `hms.json`, `recommendations.json`,
`agent.json`, `mailbox.json`, `errors.json`) with the same keys, translated values.

**All non-English content is machine-translated** (generated in one AI pass per script family,
not reviewed by a native speaker or a clinical-domain expert) and should be treated as a
prototype-quality first draft, not field/production-ready copy — the same "flag it, don't claim
it's more finished than it is" convention `AGENTS.md` already applies to backend stubs. Review
status per locale is tracked in `frontend/lib/i18n/locales.ts`'s `Locale.reviewed` field (`false`
until a native speaker has actually checked a locale's files); nothing in the product UI itself
currently surfaces this flag to end users.

Two locales carry extra uncertainty even by that standard: **Manipuri/Meitei (`mni`, Meetei Mayek
script)** and **Santali (`sat`, Ol Chiki script)** are both under-represented in the data any LLM
is trained on, so translation quality there is the least certain of the 20 non-English locales —
prioritize these two first if/when a native-speaker review pass happens.

**Known gap**: `warehouse.json` does not exist yet. `app/warehouse/page.tsx` and
`app/orders/new/page.tsx` (plus their supporting components `orders/CandidateActionCard.tsx`,
`warehouse/OrderStageDetail.tsx`, `agent/ChatThread.tsx`) were mid-rewrite by a separate,
uncommitted, concurrent workstream (an offline order-sync feature and an agentic order-composer
UI) at the time this i18n pass ran — translating them then would have meant hand-editing someone
else's in-flight code with no context on where it was headed. Extract and translate these once
that work settles/commits, following the exact same pattern as every other namespace file here.

## Adding a locale later

1. Add an entry to `LOCALES` in `frontend/lib/i18n/locales.ts` (code, autonym, script, Google Fonts
   family if non-Latin).
2. Add the same code to `SUPPORTED_LOCALES` in `backend/ops/locales.py` (keep the two lists in
   sync — the backend validates `users.preferred_locale` against its own copy).
3. Create `public/locales/<code>/*.json` mirroring every key in `en/`'s namespace files.
