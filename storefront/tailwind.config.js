/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Chick Shack brand: charcoal shell with a hot flame accent.
        ink: { DEFAULT: "#12100f", soft: "#1c1917", line: "#2a2523" },
        flame: { DEFAULT: "#e2361d", dark: "#b82413", light: "#ff5c42" },
        ember: "#f5a524",
        cream: "#faf7f2",
      },
      fontFamily: {
        display: ["'Archivo Black'", "Impact", "system-ui", "sans-serif"],
        sans: ["'Inter'", "system-ui", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
};
