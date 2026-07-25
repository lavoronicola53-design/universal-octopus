import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#08060D",
          900: "#0D0A16",
          850: "#120E1E",
          800: "#171128",
          700: "#241A3D",
          600: "#362A55",
        },
        ink: {
          100: "#ECE8F5",
          300: "#C4BAD9",
          500: "#8B7FA8",
          700: "#564B70",
        },
        violet: {
          400: "#B98CFF",
          500: "#9D5CFF",
          600: "#7E3BE8",
        },
        bull: "#3BD1A0",
        bear: "#E15577",
        scenario: {
          1: "#9D5CFF",
          2: "#5C8FFF",
          3: "#D46CE8",
          4: "#6CE8C4",
          5: "#B98CFF",
        },
      },
      fontFamily: {
        mono: ["'IBM Plex Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["'IBM Plex Sans'", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 0 0 1px rgba(157,92,255,0.08), 0 8px 24px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
