/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: "#8D5EE6",
        background: "#F5F3FA",
        card: "#FFFFFF",
        accent: "#E5DEFF",
        muted: "#94A3B8",
        success: "#10B981",
        warning: "#F59E0B",
        error: "#EF4444",
      },
    },
  },
  plugins: [],
};
