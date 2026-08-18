/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        "secondary-container": "#00c705",
        "on-surface": "#e2e2e9",
        "on-surface-variant": "#d1c5ac",
        "error-container": "#93000a",
        error: "#ffb4ab",
        secondary: "#3ce42f",
        "surface-container-lowest": "#0c0e13",
        tertiary: "#ffe4b1",
        primary: "#ffe5a0",
        surface: "#111318",
        outline: "#9a9078",
        "primary-container": "#f5c518",
        "surface-container-highest": "#33353a",
        "on-primary-container": "#695200",
        "surface-container-low": "#1a1b21",
        "surface-container-high": "#282a2f",
        "surface-container": "#1e1f25",
        "outline-variant": "#4e4633",
        background: "#111318",
        "tertiary-container": "#ffc11e",
        "on-primary": "#3d2f00",
        "on-background": "#e2e2e9",
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
        full: "9999px",
      },
      spacing: {
        "sidebar-width": "300px",
        "margin-mobile": "16px",
        gutter: "24px",
        "stack-gap": "12px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
