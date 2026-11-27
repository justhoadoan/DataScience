import { useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";
const storageKey = "hanoirent-theme";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* System appearance also works when storage is unavailable. */
    }
    return "system";
  });

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved =
        theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved;
    };
    apply();
    try {
      localStorage.setItem(storageKey, theme);
    } catch {
      /* Keep the current session usable. */
    }
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);

  return { theme, setTheme };
}
