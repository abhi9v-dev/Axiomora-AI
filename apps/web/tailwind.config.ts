import type { Config } from "tailwindcss";

// Visual direction (docs/05_FRONTEND_UX.md): neutral background, indigo primary
// accent, green reserved for verified status, amber for warnings, red for
// blocked actions.
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#4f46e5",
          foreground: "#eef2ff",
        },
        verified: "#16a34a",
        warning: "#d97706",
        blocked: "#dc2626",
      },
    },
  },
  plugins: [],
};

export default config;
