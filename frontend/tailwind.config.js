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
          950: "#030914",
          900: "#061225",
          850: "#071426",
          800: "#0A1A30"
        },
        ember: {
          500: "#ff7a00",
          600: "#ff6500",
          700: "#ff4d00"
        }
      },
      boxShadow: {
        ember: "0 20px 70px rgba(255, 122, 0, 0.22)",
        navy: "0 30px 120px rgba(0, 0, 0, 0.5)"
      }
    }
  },
  plugins: []
};
