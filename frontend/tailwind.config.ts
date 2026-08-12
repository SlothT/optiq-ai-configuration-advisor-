import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#121826",
        paper: "#f7f3ea",
        sand: "#eadfcf",
        accent: "#ff6b35",
        accentSoft: "#ffb38c",
      },
      boxShadow: {
        panel: "0 18px 60px rgba(18, 24, 38, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
