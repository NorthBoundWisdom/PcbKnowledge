import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface ShellState {
  navCollapsed: boolean;
  setNavCollapsed: (collapsed: boolean) => void;
  toggleNav: () => void;
}

export const useShellStore = create<ShellState>()(
  persist(
    (set) => ({
      navCollapsed: false,
      setNavCollapsed: (navCollapsed) => set({ navCollapsed }),
      toggleNav: () => set((state) => ({ navCollapsed: !state.navCollapsed })),
    }),
    {
      name: "pcbknowledge-curator-shell-v1",
      storage: createJSONStorage(() => localStorage),
      partialize: ({ navCollapsed }) => ({ navCollapsed }),
    },
  ),
);
