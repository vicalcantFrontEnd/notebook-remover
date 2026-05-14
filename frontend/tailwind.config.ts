import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ctp: {
          base:     "#1e1e2e",
          mantle:   "#181825",
          crust:    "#11111b",
          surface0: "#313244",
          surface1: "#45475a",
          surface2: "#585b70",
          overlay0: "#6c7086",
          overlay1: "#7f849c",
          text:     "#cdd6f4",
          subtext0: "#a6adc8",
          subtext1: "#bac2de",
          blue:     "#89b4fa",
          red:      "#f38ba8",
          green:    "#a6e3a1",
          peach:    "#fab387",
          mauve:    "#cba6f7",
          yellow:   "#f9e2af",
          teal:     "#94e2d5",
          lavender: "#b4befe",
        },
      },
      animation: {
        shimmer: "shimmer 1.5s infinite",
      },
      keyframes: {
        shimmer: {
          "0%":   { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
