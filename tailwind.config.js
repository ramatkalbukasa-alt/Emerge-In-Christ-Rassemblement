module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.py",
    "./apps/**/templates/**/*.html"
  ],
  theme: {
    extend: {
      colors: {
        bauhaus: {
          canvas: "#F0F0F0",
          paper: "#FFFFFF",
          ink: "#121212",
          muted: "#E0E0E0",
          slate: "#4A4A4A",
          red: "#D02020",
          blue: "#1040C0",
          yellow: "#F0C020",
          cream: "#FFF9C4"
        }
      },
      fontFamily: {
        sans: ["Outfit", "ui-sans-serif", "system-ui", "sans-serif"]
      },
      boxShadow: {
        "hard-sm": "3px 3px 0 0 #121212",
        hard: "4px 4px 0 0 #121212",
        "hard-md": "6px 6px 0 0 #121212",
        "hard-lg": "8px 8px 0 0 #121212",
        "hard-paper": "4px 4px 0 0 #FFFFFF"
      },
      lineHeight: {
        display: "0.9"
      },
      backgroundImage: {
        "dot-grid": "radial-gradient(#121212 1.5px, transparent 1.5px)",
        "dot-grid-light": "radial-gradient(#FFFFFF 2px, transparent 2px)"
      },
      backgroundSize: {
        grid: "20px 20px"
      }
    }
  },
  plugins: [require("@tailwindcss/forms")({ strategy: "class" })]
};
