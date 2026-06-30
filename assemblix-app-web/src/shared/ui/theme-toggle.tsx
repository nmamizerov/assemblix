import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useTheme } from "@/shared/lib/theme-context";
import { Switch } from "@/shared/ui/switch";
import { Label } from "@/shared/ui/label";

// Hook to detect system theme preference
const useSystemDark = () => {
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== "undefined") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    return false;
  });

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");

    // Update state in case it changed between init and effect (unlikely but safe)
    // Actually, simply subscribing is enough if init was correct.
    // But to be super safe and reactive:
    const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, []);

  return isDark;
};

export const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();
  const systemIsDark = useSystemDark();

  // Determine effective state
  const isChecked = theme === "dark" || (theme === "system" && systemIsDark);

  const handleCheckedChange = (checked: boolean) => {
    setTheme(checked ? "dark" : "light");
  };

  return (
    <div className="flex items-center space-x-2">
      <Switch
        id="theme-mode"
        checked={isChecked}
        onCheckedChange={handleCheckedChange}
      />
      <Label htmlFor="theme-mode" className="sr-only">
        Toggle theme
      </Label>
      {isChecked ? (
        <Moon className="h-4 w-4 text-slate-900 dark:text-slate-50" />
      ) : (
        <Sun className="h-4 w-4 text-slate-900 dark:text-slate-50" />
      )}
    </div>
  );
};
