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
        "tint-red-wash-strong": "var(--tint-red-wash-strong)",
        "tint-green-wash": "var(--tint-green-wash)",
        "tint-green-wash-strong": "var(--tint-green-wash-strong)",
        "tint-blue-wash": "var(--tint-blue-wash)",
        "tint-blue-wash-strong": "var(--tint-blue-wash-strong)",
        "fill-thick": "var(--fill-thick)",
        "fill-regular": "var(--fill-regular)",
        "fill-thin": "var(--fill-thin)",
        "brand-teal": "var(--brand-teal)",
        "brand-teal-wash": "var(--brand-teal-wash)",
        "brand-green": "var(--brand-green)",
        "brand-green-wash": "var(--brand-green-wash)",
        "brand-orange": "var(--brand-orange)",
        "brand-orange-wash": "var(--brand-orange-wash)",
        "brand-gold": "var(--brand-gold)",
        "brand-gold-wash": "var(--brand-gold-wash)",
      },
      backgroundImage: {
        brand: "var(--brand-gradient)",
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
      boxShadow: {
        // Soft, low-contrast elevation — Apple HIG cards read as "raised paper", never a hard
        // drop shadow. Two-layer (tight + diffuse) for a more natural falloff than a single blur.
        card: "0 1px 2px rgba(0,0,0,0.04), 0 2px 10px rgba(0,0,0,0.045)",
        "card-hover": "0 2px 4px rgba(0,0,0,0.06), 0 10px 24px rgba(0,0,0,0.08)",
        popover: "0 8px 16px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.06)",
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
        shimmer: {
          from: { backgroundPosition: "150% 0" },
          to: { backgroundPosition: "-50% 0" },
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
        "pop-in": {
          "0%": { opacity: "0", transform: "scale(0.6)" },
          "60%": { opacity: "1", transform: "scale(1.08)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 0 0 var(--tint-red-wash)" },
          "50%": { boxShadow: "0 0 0 6px transparent" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translateX(10px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-left": {
          from: { opacity: "0", transform: "translateX(-10px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "underline-grow": {
          from: { transform: "scaleX(0)" },
          to: { transform: "scaleX(1)" },
        },
        "toast-in": {
          from: { opacity: "0", transform: "translateY(-12px) scale(0.96)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        "toast-out": {
          from: { opacity: "1", transform: "translateY(0) scale(1)", maxHeight: "80px" },
          to: { opacity: "0", transform: "translateY(-8px) scale(0.96)", maxHeight: "0" },
        },
        // Path length of Icon's "checkCircle" (checkmark + circle in one path), measured via
        // getTotalLength() — the checkmark subpath alone is ~8.5 of the total ~65, so animating
        // the whole path's dashoffset draws the checkmark first (~13% of the duration) and then
        // sweeps the circle around it, reading as "seal of approval" rather than a generic reveal.
        "draw-check": {
          from: { strokeDashoffset: "65" },
          to: { strokeDashoffset: "0" },
        },
        materialize: {
          from: { opacity: "0", transform: "scale(0.985) translateY(6px)", filter: "blur(3px)" },
          to: { opacity: "1", transform: "scale(1) translateY(0)", filter: "blur(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 320ms ease-out both",
        "fade-in-up": "fade-in-up 420ms cubic-bezier(0.16,1,0.3,1) both",
        "scale-in": "scale-in 220ms cubic-bezier(0.16,1,0.3,1) both",
        "sheet-up": "sheet-up 320ms cubic-bezier(0.16,1,0.3,1) both",
        "skeleton-pulse": "skeleton-pulse 1.4s ease-in-out infinite",
        shimmer: "shimmer 1.8s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.4,0,0.6,1) infinite",
        "draw-line": "draw-line 1.8s ease-in-out infinite",
        "bounce-dot": "bounce-dot 1.2s ease-in-out infinite",
        breathe: "breathe 3.2s ease-in-out infinite",
        "pop-in": "pop-in 380ms cubic-bezier(0.34,1.56,0.64,1) both",
        "glow-pulse": "glow-pulse 1.8s ease-in-out infinite",
        "slide-in-right": "slide-in-right 260ms cubic-bezier(0.16,1,0.3,1) both",
        "slide-in-left": "slide-in-left 260ms cubic-bezier(0.16,1,0.3,1) both",
        "toast-in": "toast-in 320ms cubic-bezier(0.16,1,0.3,1) both",
        "toast-out": "toast-out 220ms cubic-bezier(0.4,0,1,1) both",
        "draw-check": "draw-check 420ms 200ms cubic-bezier(0.65,0,0.35,1) both",
        materialize: "materialize 360ms cubic-bezier(0.16,1,0.3,1) both",
        "underline-grow": "underline-grow 260ms cubic-bezier(0.16,1,0.3,1) both",
      },
    },
  },
  plugins: [],
};

export default config;
