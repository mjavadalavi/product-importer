import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ["var(--font-vazirmatn)", "system-ui", "sans-serif"],
        vazirmatn: ["var(--font-vazirmatn)", "system-ui", "sans-serif"],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
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
        // ─────────────────────────────────────────────────────────────
        // Basalam vendor design system (from @timcheh/components/styles)
        // ─────────────────────────────────────────────────────────────
        bs: {
          primary: {
            DEFAULT: "#1c2575",
            100: "#eff0fb",
            200: "#ced1f3",
            300: "#9ca4e7",
            400: "#6b76db",
            500: "#3a49cf",
            600: "#2834a4",
            700: "#101542",
            800: "#040510",
            900: "#010205",
          },
          success: {
            DEFAULT: "#348409",
            100: "#ebf3e6",
            200: "#d6e6ce",
            300: "#d6e6ce",
            400: "#71a953",
            500: "#5d9d3a",
            600: "#489022",
            700: "#265f06",
            800: "#1e4c05",
            900: "#183d04",
          },
          warning: {
            DEFAULT: "#fbb30e",
            100: "#fff7e7",
            200: "#fef0cf",
            300: "#fdd987",
            400: "#fcca56",
            500: "#e2a10d",
            600: "#b5810a",
            700: "#916708",
            800: "#745206",
            900: "#5d4205",
          },
          danger: {
            DEFAULT: "#ba132e",
            100: "#faeff1",
            200: "#f8e7ea",
            300: "#f1d0d5",
            400: "#dc8997",
            500: "#cf5a6d",
            600: "#c84258",
            700: "#c12b43",
            800: "#6b0b1a",
            900: "#560915",
          },
          blue: {
            DEFAULT: "#3086d1",
            100: "#eaf3fa",
            200: "#d6e7f6",
            300: "#97c3e8",
            400: "#6eaadf",
            500: "#599eda",
            600: "#4592d6",
            700: "#226196",
            800: "#1b4e78",
            900: "#163e60",
          },
          gray: {
            "025": "#fafafb",
            "050": "#f3f3f4",
            100: "#e7e7e9",
            200: "#cfced3",
            300: "#b6b6bd",
            400: "#9e9ea7",
            500: "#868590",
            600: "#6e6d7a",
            700: "#565564",
            800: "#3d3d4e",
            900: "#252438",
          },
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
