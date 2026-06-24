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
          ink: "#F2F0E4",
          muted: "#A6A095",
          line: "rgba(212, 175, 55, 0.32)",
          paper: "#141414",
          wash: "#0A0A0A",
          green: "#D4AF37",
          gold: "#D4AF37",
          blue: "#1E3D59",
          black: "#0A0A0A",
          cream: "#F2F0E4",
          charcoal: "#141414",
          pewter: "#888888"
        }
      },
      fontFamily: {
        sans: ["Josefin Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Marcellus", "serif"]
      }
    }
  },
  plugins: [require("@tailwindcss/forms")]
};
