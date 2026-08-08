import { alpha, createTheme } from "@mui/material/styles";

const ink = "#17222f";
const blue = "#1769aa";
const amber = "#c77800";

export const curatorTheme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: blue,
      dark: "#0d4775",
      light: "#4e91c5",
    },
    secondary: {
      main: amber,
    },
    background: {
      default: "#f3f6f8",
      paper: "#ffffff",
    },
    text: {
      primary: ink,
      secondary: "#596776",
    },
    divider: "#dce3e8",
  },
  shape: {
    borderRadius: 8,
  },
  spacing: 8,
  typography: {
    fontFamily:
      'Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h1: {
      fontSize: "1.75rem",
      fontWeight: 650,
      letterSpacing: "-0.02em",
    },
    h2: {
      fontSize: "1.25rem",
      fontWeight: 650,
    },
    button: {
      fontWeight: 650,
      textTransform: "none",
    },
    overline: {
      fontSize: "0.68rem",
      fontWeight: 700,
      letterSpacing: "0.08em",
    },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: "1px solid #dce3e8",
          boxShadow: "0 1px 2px rgba(23, 34, 47, 0.04)",
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          "&.Mui-selected": {
            backgroundColor: alpha(blue, 0.1),
            color: "#0d4775",
          },
        },
      },
    },
  },
});
