/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          dark: "var(--color-primary-dark)",
          light: "var(--color-primary-light)",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Legacy theme compatibility mappings
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
        "success-bg": "var(--color-success-bg)",
        "success-text": "var(--color-success-text)",
        error: "#EF4444",
        "error-container": "rgba(239, 68, 68, 0.15)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      spacing: {
        gutter: "24px",
        "stack-sm": "8px",
        "stack-md": "16px",
        "stack-lg": "32px",
        "margin-page": "40px",
        unit: "4px",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        "display-serif": ["Fraunces", "serif"],
        "display-serif-alt": ["Instrument Serif", "serif"],
        "label-md": ["JetBrains Mono", "monospace"],
        "body-sm": ["Inter", "sans-serif"],
        "body-md": ["Inter", "sans-serif"],
        "body-lg": ["Inter", "sans-serif"],
        "headline-lg-mobile": ["Inter", "sans-serif"],
        "headline-md": ["Inter", "sans-serif"],
        "headline-lg": ["Inter", "sans-serif"],
        "display-lg": ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
