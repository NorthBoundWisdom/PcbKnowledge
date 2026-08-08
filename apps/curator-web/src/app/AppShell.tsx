import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import AssignmentTurnedInOutlinedIcon from "@mui/icons-material/AssignmentTurnedInOutlined";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import MenuBookOutlinedIcon from "@mui/icons-material/MenuBookOutlined";
import PlagiarismOutlinedIcon from "@mui/icons-material/PlagiarismOutlined";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import WorkHistoryOutlinedIcon from "@mui/icons-material/WorkHistoryOutlined";
import {
  AppBar,
  Avatar,
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  InputAdornment,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import type { ElementType } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { useShellStore } from "../state/shell-store";
import { useRuntimeConfig } from "./use-runtime-config";

const expandedWidth = 224;
const collapsedWidth = 64;

interface NavigationItem {
  icon: ElementType;
  label: string;
  to: string;
}

interface NavigationGroup {
  items: readonly NavigationItem[];
  label: string;
}

const navigationGroups: readonly NavigationGroup[] = [
  {
    label: "Operate",
    items: [
      { icon: DashboardOutlinedIcon, label: "Dashboard", to: "/dashboard" },
      { icon: Inventory2OutlinedIcon, label: "Intake", to: "/intake" },
      { icon: ArticleOutlinedIcon, label: "Documents", to: "/documents" },
      { icon: AssignmentTurnedInOutlinedIcon, label: "Review", to: "/review" },
    ],
  },
  {
    label: "Curate",
    items: [
      { icon: AccountTreeOutlinedIcon, label: "Entities", to: "/entities" },
      { icon: MenuBookOutlinedIcon, label: "Knowledge", to: "/knowledge" },
      { icon: PlagiarismOutlinedIcon, label: "Search", to: "/search" },
    ],
  },
  {
    label: "Assure",
    items: [
      { icon: FactCheckOutlinedIcon, label: "Evals", to: "/evals" },
      { icon: HistoryOutlinedIcon, label: "Audit", to: "/audit" },
    ],
  },
  {
    label: "Control",
    items: [
      { icon: AdminPanelSettingsOutlinedIcon, label: "Admin", to: "/admin" },
      { icon: WorkHistoryOutlinedIcon, label: "Jobs", to: "/jobs" },
    ],
  },
];

function Navigation({ collapsed }: { collapsed: boolean }) {
  const location = useLocation();

  return (
    <Box component="nav" sx={{ flex: 1, overflowY: "auto", px: 1, py: 1.5 }}>
      {navigationGroups.map((group, groupIndex) => (
        <Box key={group.label} sx={{ mb: 1.5 }}>
          {!collapsed && (
            <Typography color="text.secondary" sx={{ px: 1.5, py: 0.5 }} variant="overline">
              {group.label}
            </Typography>
          )}
          <List dense disablePadding>
            {group.items.map((item) => {
              const selected =
                location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
              const Icon = item.icon;
              const button = (
                <ListItemButton
                  aria-label={item.label}
                  component={Link}
                  selected={selected}
                  sx={{ justifyContent: collapsed ? "center" : "flex-start", mb: 0.25, minHeight: 40 }}
                  to={item.to}
                >
                  <ListItemIcon sx={{ color: "inherit", minWidth: collapsed ? 0 : 36 }}>
                    <Icon fontSize="small" />
                  </ListItemIcon>
                  {!collapsed && <ListItemText primary={item.label} slotProps={{ primary: { variant: "body2" } }} />}
                </ListItemButton>
              );

              return collapsed ? (
                <Tooltip key={item.to} placement="right" title={item.label}>
                  {button}
                </Tooltip>
              ) : (
                <Box key={item.to}>{button}</Box>
              );
            })}
          </List>
          {groupIndex < navigationGroups.length - 1 && collapsed && <Divider sx={{ my: 1.5 }} />}
        </Box>
      ))}
    </Box>
  );
}

export function AppShell() {
  const config = useRuntimeConfig();
  const navCollapsed = useShellStore((state) => state.navCollapsed);
  const toggleNav = useShellStore((state) => state.toggleNav);
  const drawerWidth = navCollapsed ? collapsedWidth : expandedWidth;

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        color="inherit"
        elevation={0}
        position="fixed"
        sx={{ borderBottom: 1, borderColor: "divider", ml: `${drawerWidth}px`, width: `calc(100% - ${drawerWidth}px)` }}
      >
        <Toolbar disableGutters sx={{ gap: 2, minHeight: "56px !important", px: 2.5 }}>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Typography sx={{ fontWeight: 700 }} variant="body2">
              Evidence Workspace
            </Typography>
            <Chip label="No project selected" size="small" variant="outlined" />
          </Stack>
          <TextField
            aria-label="Global search unavailable in foundation"
            disabled
            placeholder="Global search arrives with M4"
            size="small"
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchRoundedIcon fontSize="small" />
                  </InputAdornment>
                ),
              },
            }}
            sx={{ ml: "auto", width: 320 }}
          />
          <Chip color="primary" label={config.deploymentLabel} size="small" variant="outlined" />
          <Avatar aria-label="Signed-out user placeholder" sx={{ bgcolor: "text.primary", fontSize: 12, height: 30, width: 30 }}>
            M0
          </Avatar>
        </Toolbar>
      </AppBar>

      <Drawer
        open
        sx={{
          flexShrink: 0,
          width: drawerWidth,
          "& .MuiDrawer-paper": {
            bgcolor: "#f9fbfc",
            borderRightColor: "divider",
            boxSizing: "border-box",
            overflowX: "hidden",
            transition: (theme) => theme.transitions.create("width"),
            width: drawerWidth,
          },
        }}
        variant="permanent"
      >
        <Stack direction="row" sx={{ alignItems: "center", minHeight: 56, px: navCollapsed ? 1 : 1.5 }}>
          <Box
            aria-hidden="true"
            sx={{ bgcolor: "text.primary", borderRadius: 1, color: "white", display: "grid", fontSize: 11, fontWeight: 800, height: 30, placeItems: "center", width: 30 }}
          >
            PK
          </Box>
          {!navCollapsed && (
            <Box sx={{ ml: 1.25, minWidth: 0 }}>
              <Typography noWrap sx={{ fontWeight: 750 }} variant="body2">
                PcbKnowledge
              </Typography>
              <Typography color="text.secondary" noWrap variant="caption">
                Curator Web
              </Typography>
            </Box>
          )}
          <Tooltip title={navCollapsed ? "Expand navigation" : "Collapse navigation"}>
            <IconButton aria-label={navCollapsed ? "Expand navigation" : "Collapse navigation"} onClick={toggleNav} size="small" sx={{ ml: "auto" }}>
              {navCollapsed ? <ChevronRightRoundedIcon /> : <ChevronLeftRoundedIcon />}
            </IconButton>
          </Tooltip>
        </Stack>
        <Divider />
        <Navigation collapsed={navCollapsed} />
        {!navCollapsed && (
          <Stack spacing={0.5} sx={{ borderTop: 1, borderColor: "divider", p: 2 }}>
            <Typography color="text.secondary" variant="caption">
              API boundary
            </Typography>
            <Typography sx={{ fontWeight: 650 }} variant="caption">
              Generated OpenAPI client
            </Typography>
          </Stack>
        )}
      </Drawer>

      <Box
        component="main"
        sx={{ flexGrow: 1, minWidth: 0, px: 4, py: 3.5, pt: "84px", transition: (theme) => theme.transitions.create("margin") }}
      >
        <Outlet />
      </Box>

      <Box
        role="status"
        sx={{
          alignItems: "center",
          bgcolor: "warning.dark",
          bottom: 0,
          color: "warning.contrastText",
          display: { lg: "none", xs: "flex" },
          fontSize: 13,
          fontWeight: 650,
          justifyContent: "center",
          left: 0,
          minHeight: 40,
          position: "fixed",
          right: 0,
          zIndex: (theme) => theme.zIndex.tooltip,
        }}
      >
        Curator Web requires a desktop workspace of at least 1440 × 900 for review workflows.
      </Box>
    </Box>
  );
}
