/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        space: { 950: "#050914", 900: "#080f1e", 850: "#0b1425", 800: "#101d31" },
        sun: "#f5b84b",
        earth: "#5ba8ff",
        signal: "#52d6a5",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
