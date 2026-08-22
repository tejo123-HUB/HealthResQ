"use client";

import { useTranslation } from "react-i18next";
import { Icon } from "@/components/hig/Icon";
import { SheetShell } from "@/components/hig/Sheet";
import { LOCALES } from "@/lib/i18n/locales";

/** Plain scrollable tap-to-pick list, not a `<select>` and not a search box — per the "selecting >
 * typing >> searching" policy, even at 21 options. Each row shows only the language's own autonym
 * (never an English translation of the name), since a lazy/illiterate-persona user is reading
 * their own script to find it, not English. */
export function LanguageSheet({
  open,
  current,
  onSelect,
  onDismiss,
}: {
  open: boolean;
  current: string;
  onSelect: (code: string) => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation("common");

  return (
    <SheetShell
      open={open}
      onDismiss={onDismiss}
      className="p-3 flex flex-col gap-1 text-left max-h-[80vh]"
      maxWidthClass="sm:max-w-xs"
    >
      <p className="text-headline px-2 pb-2 pt-1">{t("language")}</p>
      <div className="overflow-y-auto flex flex-col gap-0.5">
        {LOCALES.map((locale) => (
          <button
            key={locale.code}
            onClick={() => onSelect(locale.code)}
            className={`flex items-center justify-between gap-3 min-h-[2.75rem] px-3 rounded-hig text-body transition-hig active:scale-[0.98] ${
              locale.code === current
                ? "bg-tint-blue-wash text-tint-blue font-medium"
                : "text-label hover:bg-fill-regular"
            }`}
          >
            <span>{locale.autonym}</span>
            {locale.code === current && <Icon name="check" className="w-4 h-4 shrink-0" />}
          </button>
        ))}
      </div>
    </SheetShell>
  );
}
