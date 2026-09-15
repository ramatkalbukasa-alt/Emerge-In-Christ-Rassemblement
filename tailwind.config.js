module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.py",
    "./apps/**/templates/**/*.html"
  ],
  theme: {
    extend: {
      colors: {
        // ── Linear / Modern design system ──────────────────────────────
        bg: {
          deep: "#020203",
          base: "#050506",
          elevated: "#0a0a0c"
        },
        fg: {
          DEFAULT: "rgb(var(--fg) / <alpha-value>)",
          muted: "rgb(var(--muted) / <alpha-value>)",
          subtle: "rgba(255,255,255,0.60)"
        },
        accent: {
          DEFAULT: "#C90800",
          bright: "rgb(var(--accent-text) / <alpha-value>)",
          glow: "rgba(201,8,0,0.2)"
        },
        gold: "#FFD84D",
        bronze: "#9A642E"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"]
      }
    }
  },
  plugins: [require("@tailwindcss/forms")]
};
