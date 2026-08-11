/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Redesigned Brand Palette utilizing CSS Variables
        primary: "var(--color-primary)",
        "primary-dark": "var(--color-primary-dark)",
        "primary-light": "var(--color-primary-light)",
        secondary: "var(--color-secondary)",
        "secondary-light": "var(--color-secondary-light)",
        
        background: "var(--color-background)",
        surface: "var(--color-surface)",
        "surface-variant": "var(--color-surface-secondary)",
        "surface-container": "var(--color-surface-secondary)",
        "surface-container-low": "var(--color-surface-secondary)",
        "surface-container-high": "var(--color-surface-secondary)",
        "surface-container-highest": "var(--color-secondary-light)",
        "surface-container-lowest": "var(--color-background)",
        
        outline: "var(--color-text-muted)",
        "outline-variant": "var(--color-border)",
        
        "on-surface": "var(--color-text-primary)",
        "on-surface-variant": "var(--color-text-secondary)",
        "on-background": "var(--color-text-primary)",
        
        "primary-container": "var(--color-primary)",
        "on-primary-container": "#FFFFFF",
        "secondary-container": "var(--color-primary-dark)",
        "on-secondary-container": "#FFFFFF",
        
        // Status indicator mappings
        "success-bg": "var(--color-success-bg)",
        "success-text": "var(--color-success-text)",
        
        error: "#EF4444",
        "error-container": "rgba(239, 68, 68, 0.15)",
        
        // Material fix fallbacks
        "outline-variant-dark": "#23342A",
        "tertiary": "#7FA692"
      },
      borderRadius: {
        "sm": "0.25rem",
        "DEFAULT": "0.5rem",
        "md": "0.75rem",
        "lg": "1rem",
        "xl": "1.5rem",
        "full": "9999px"
      },
      spacing: {
        "gutter": "24px",
        "stack-sm": "8px",
        "stack-md": "16px",
        "stack-lg": "32px",
        "margin-page": "40px",
        "unit": "4px"
      },
      fontFamily: {
        "display-serif": ["Fraunces", "serif"],
        "display-serif-alt": ["Instrument Serif", "serif"],
        "label-md": ["JetBrains Mono", "monospace"],
        "body-sm": ["Inter", "sans-serif"],
        "body-md": ["Inter", "sans-serif"],
        "body-lg": ["Inter", "sans-serif"],
        "headline-lg-mobile": ["Inter", "sans-serif"],
        "headline-md": ["Inter", "sans-serif"],
        "headline-lg": ["Inter", "sans-serif"],
        "display-lg": ["Inter", "sans-serif"]
      }
    },
  },
  plugins: [],
}
