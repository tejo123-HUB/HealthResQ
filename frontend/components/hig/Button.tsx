"use client";

import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "destructive";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-tint-blue text-white hover:bg-[color-mix(in_srgb,var(--tint-blue)_88%,black)] hover:shadow-card-hover",
  secondary: "bg-fill-regular text-label hover:bg-fill-thick",
  destructive: "bg-tint-red text-white hover:bg-[color-mix(in_srgb,var(--tint-red)_88%,black)] hover:shadow-card-hover",
};

// A soft diagonal highlight that sweeps across on hover — reserved for `primary`, the one button
// per screen that's actually the main call to action; adding it to every button would read as
// noise instead of emphasis. Pure CSS (translate + transition, no JS, no keyframe loop running
// while idle) so it costs nothing until a pointer actually hovers the button.
const SHINE =
  "before:content-[''] before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/30 before:to-transparent before:-translate-x-[120%] before:skew-x-[-20deg] before:transition-transform before:duration-700 before:ease-out hover:before:translate-x-[120%]";

export function Button({
  variant = "primary",
  className = "",
  disabled,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      disabled={disabled}
      className={`relative overflow-hidden isolate transition-hig text-headline rounded-hig px-4 min-h-[44px] ${VARIANT_CLASSES[variant]} ${
        variant === "primary" && !disabled ? SHINE : ""
      } ${disabled ? "opacity-40 cursor-not-allowed" : "active:opacity-70 active:scale-[0.97]"} ${className}`}
    >
      <span className="relative z-10 flex items-center justify-center gap-2">{children}</span>
    </button>
  );
}
