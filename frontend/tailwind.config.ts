import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["selector", '[data-theme="dark"]'],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-secondary": "var(--bg-secondary)",
        "bg-tertiary": "var(--bg-tertiary)",
        label: "var(--label)",
        "label-secondary": "var(--label-secondary)",
        "label-tertiary": "var(--label-tertiary)",
        "label-quaternary": "var(--label-quaternary)",
        separator: "var(--separator)",
        "tint-blue": "var(--tint-blue)",
        "tint-green": "var(--tint-green)",
        "tint-orange": "var(--tint-orange)",
        "tint-red": "var(--tint-red)",
        "tint-orange-wash": "var(--tint-orange-wash)",
        "tint-orange-wash-strong": "var(--tint-orange-wash-strong)",
        "tint-red-wash": "var(--tint-red-wash)",
        "tint-green-wash": "var(--tint-green-wash)",
        "tint-blue-wash": "var(--tint-blue-wash)",
        "fill-thick": "var(--fill-thick)",
        "fill-regular": "var(--fill-regular)",
        "fill-thin": "var(--fill-thin)",
        "brand-teal": "var(--brand-teal)",
        "brand-teal-wash": "var(--brand-teal-wash)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
      borderRadius: {
        hig: "12px",
      },
      spacing: {
        4.5: "1.125rem",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.94)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "sheet-up": {
          from: { transform: "translateY(100%)" },
          to: { transform: "translateY(0)" },
        },
        "skeleton-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.6" },
          "70%": { transform: "scale(1.5)", opacity: "0" },
          "100%": { transform: "scale(1.5)", opacity: "0" },
        },
        "draw-line": {
          to: { strokeDashoffset: "0" },
        },
        "bounce-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        "breathe": {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.05)" },
        },
      },
      animation: {
        "fade-in": "fade-in 320ms ease-out both",
        "fade-in-up": "fade-in-up 420ms cubic-bezier(0.16,1,0.3,1) both",
        "scale-in": "scale-in 220ms cubic-bezier(0.16,1,0.3,1) both",
        "sheet-up": "sheet-up 320ms cubic-bezier(0.16,1,0.3,1) both",
        "skeleton-pulse": "skeleton-pulse 1.4s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.4,0,0.6,1) infinite",
        "draw-line": "draw-line 1.8s ease-in-out infinite",
        "bounce-dot": "bounce-dot 1.2s ease-in-out infinite",
        breathe: "breathe 3.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
