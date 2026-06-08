/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      // Reskin tokens reference the design-system CSS variables (single source of
      // truth lives in :root of src/design-system.css — no duplicated hex here).
      fontFamily: {
        serif: ["var(--serif)"],
        sans: ["var(--sans)"],
        mono: ["var(--mono)"],
        display: ["var(--serif)"]
      },
      colors: {
        // --- new dark design system (var-backed) ---
        bg: "var(--bg)",
        "sidebar-bg": "var(--sidebar-bg)",
        card: "var(--card)",
        "card-2": "var(--card-2)",
        "card-border": "var(--card-border)",
        "card-border-2": "var(--card-border-2)",
        hairline: "var(--hairline)",
        "pastel-bluegray": "var(--pastel-bluegray)",
        "pastel-sage": "var(--pastel-sage)",
        "pastel-cream": "var(--pastel-cream)",
        "pastel-lavender": "var(--pastel-lavender)",
        "pastel-ink": "var(--pastel-ink)",
        text: "var(--text)",
        "text-dim": "var(--text-dim)",
        muted: "var(--muted)",
        label: "var(--label)",
        green: "var(--green)",
        "green-soft": "var(--green-soft)",
        amber: "var(--amber)",
        "amber-soft": "var(--amber-soft)",
        red: "var(--red)",
        "red-soft": "var(--red-soft)",
        indigo: "var(--indigo)",
        "indigo-soft": "var(--indigo-soft)",
        // --- legacy Claude-baseline palette: retained until each component is
        //     migrated off it in later reskin slices (removing now would inert
        //     ~160 existing class usages). Not part of the new design system. ---
        navy: {
          950: "#0A0F1A",
          900: "#0F1626",
          850: "#131B2C",
          800: "#1A2235"
        },
        ember: {
          400: "#FB923C",
          500: "#F97316",
          600: "#EA580C",
          700: "#C2410C"
        }
      },
      borderRadius: {
        hero: "var(--r-hero)",
        card: "var(--r-card)",
        inner: "var(--r-inner)",
        pill: "var(--r-pill)"
      },
      boxShadow: {
        ember: "0 18px 44px -18px rgba(249, 115, 22, 0.72)",
        navy: "0 34px 140px rgba(0, 0, 0, 0.58)"
      }
    }
  },
  plugins: []
};
