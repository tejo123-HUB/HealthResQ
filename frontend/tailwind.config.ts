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
        "brand-green": "var(--brand-green)",
        "brand-orange": "var(--brand-orange)",
        "brand-gold": "var(--brand-gold)",
        "brand-teal-wash": "var(--brand-teal-wash)",
        "brand-green-wash": "var(--brand-green-wash)",
        "brand-orange-wash": "var(--brand-orange-wash)",
        "brand-gold-wash": "var(--brand-gold-wash)",
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
        "shimmer": {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
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
        "blob-drift-a": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(4%, 6%) scale(1.08)" },
        },
        "blob-drift-b": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(-5%, -4%) scale(1.1)" },
        },
        "blob-drift-c": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(-3%, 5%) scale(1.06)" },
        },
      },
      animation: {
        "fade-in": "fade-in 320ms ease-out both",
        "fade-in-up": "fade-in-up 420ms cubic-bezier(0.16,1,0.3,1) both",
        "scale-in": "scale-in 220ms cubic-bezier(0.16,1,0.3,1) both",
        "sheet-up": "sheet-up 320ms cubic-bezier(0.16,1,0.3,1) both",
        shimmer: "shimmer 1.6s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.4,0,0.6,1) infinite",
        "draw-line": "draw-line 1.8s ease-in-out infinite",
        "bounce-dot": "bounce-dot 1.2s ease-in-out infinite",
        breathe: "breathe 3.2s ease-in-out infinite",
        "blob-drift-a": "blob-drift-a 11s ease-in-out infinite",
        "blob-drift-b": "blob-drift-b 13s ease-in-out infinite",
        "blob-drift-c": "blob-drift-c 9s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
