import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        shell: "#eef3f8",
        ink: "#1f2d3d",
        accent: "#4b89dc",
        mint: "#6abf9b"
      },
      boxShadow: {
        neu: "9px 9px 18px #d7dce1, -9px -9px 18px #ffffff",
        "neu-inset": "inset 6px 6px 12px #d7dce1, inset -6px -6px 12px #ffffff"
      },
      borderRadius: {
        neu: "1.5rem",
        "neu-lg": "2rem"
      }
    }
  },
  plugins: []
};

export default config;

