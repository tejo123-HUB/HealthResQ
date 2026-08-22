"""Mirrors frontend/lib/i18n/locales.ts's LOCALE_CODES exactly — the backend's allow-list for
`users.preferred_locale`. Kept as a plain set (not a DB enum) so adding a supported language later
is a one-line change in both places, not a migration to widen an enum type."""

SUPPORTED_LOCALES: frozenset[str] = frozenset(
    {
        "en", "hi", "bn", "as", "brx", "doi", "gu", "kn", "kok", "mai",
        "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te",
    }
)

DEFAULT_LOCALE = "en"
