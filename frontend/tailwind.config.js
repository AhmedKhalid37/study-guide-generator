/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        display: ["Inter", "ui-sans-serif", "system-ui"]
      },
      colors: {
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
      boxShadow: {
        ember: "0 18px 44px -18px rgba(249, 115, 22, 0.72)",
        navy: "0 34px 140px rgba(0, 0, 0, 0.58)"
      }
    }
  },
  plugins: []
};
