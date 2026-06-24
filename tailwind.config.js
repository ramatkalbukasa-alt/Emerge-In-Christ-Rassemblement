module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.py",
    "./apps/**/templates/**/*.html"
  ],
  theme: {
    extend: {
      colors: {
        ecclesia: {
          ink: "#111827",
          muted: "#4B5563",
          line: "#E5E7EB",
          paper: "#FFFFFF",
          wash: "#F7F8FA",
          green: "#166534",
          gold: "#B45309",
          blue: "#1D4ED8"
        }
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: [require("@tailwindcss/forms")]
};
