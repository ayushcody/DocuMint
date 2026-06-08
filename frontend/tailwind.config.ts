import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        muted: "#61706b",
        paper: "#f4f7fb",
        panel: "#ffffff",
        line: "#dbe3e7",
        teal: "#0f766e",
        mint: "#4ecdc4",
        amber: "#f4a127",
        coral: "#e15b64",
        berry: "#7c3aed",
        sky: "#2f80ed"
      },
      boxShadow: {
        dock: "0 16px 36px rgba(23, 32, 38, 0.10)",
        glow: "0 10px 24px rgba(15, 118, 110, 0.20)"
      }
    }
  },
  plugins: []
};

export default config;
