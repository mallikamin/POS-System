/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Ali Fish & Chips & Curry House. Taken from his printed A3 menu:
        // warm cream panels, chilli red headers, saffron yellow accents.
        // Light theme on purpose: a ~195 item, text-first menu reads better
        // dark-on-light on a phone in a bright shop or a dim living room.
        //
        //   paper   page background (DEFAULT), card surface (soft), borders (line)
        //   fg      body text; use opacity steps (fg/60) for muted text
        //   flame   brand red: buttons, active chips, prices
        //   saffron accent yellow: wordmark detail, item-number badges
        //   ember   notice / warning text (dark amber, readable on cream)
        paper: { DEFAULT: "#fbf6ec", soft: "#ffffff", line: "#eadcc4" },
        fg: "#221a14",
        flame: { DEFAULT: "#c0201b", dark: "#9a1814", light: "#c8281f" },
        saffron: { DEFAULT: "#f4b400", soft: "#fff3cc" },
        ember: "#a14a05",
      },
      fontFamily: {
        // "Ali" script wordmark, echoing the logo on the printed menu.
        script: ["'Kaushan Script'", "cursive"],
        display: ["'Oswald'", "Impact", "system-ui", "sans-serif"],
        sans: ["'Inter'", "system-ui", "-apple-system", "sans-serif"],
      },
    },
  },
  plugins: [],
};
