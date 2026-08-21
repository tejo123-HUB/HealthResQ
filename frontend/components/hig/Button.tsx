"use client";

import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "destructive";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-tint-blue text-white",
  secondary: "bg-fill-regular text-label",
  destructive: "bg-tint-red text-white",
};

export function Button({
  variant = "primary",
  className = "",
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      disabled={disabled}
      className={`transition-hig text-headline rounded-hig px-4 min-h-[44px] ${VARIANT_CLASSES[variant]} ${
        disabled ? "opacity-40 cursor-not-allowed" : "active:opacity-70 active:scale-[0.97]"
      } ${className}`}
    />
  );
}
