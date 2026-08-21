"use client";

import type { Ward } from "@/lib/api/types";

export function WardList({
  wards,
  selectedWardId,
  onSelect,
}: {
  wards: Ward[];
  selectedWardId: string | null;
  onSelect: (wardId: string) => void;
}) {
  return (
    <div className="flex gap-2 flex-wrap">
      {wards.map((w) => (
        <button
          key={w.id}
          onClick={() => onSelect(w.id)}
          className={`transition-hig text-subhead rounded-hig px-3 py-2 border ${
            selectedWardId === w.id
              ? "bg-tint-blue-wash text-tint-blue border-tint-blue"
              : "bg-bg text-label border-separator"
          }`}
        >
          {w.name}
        </button>
      ))}
    </div>
  );
}
