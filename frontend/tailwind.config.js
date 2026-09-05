/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f1420",
        panel: "#161c2b",
        panel2: "#1d2437",
        accent: "#6366f1",
        accent2: "#22d3ee",
      },
    },
  },
  plugins: [],
};
