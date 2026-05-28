import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        vault: {
          ink: "#0a0a0a",
          paper: "#fafafa",
          accent: "#1e40af",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
