import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";
import { BUNDLED_LANGS } from "@/shared/i18n";
import { LANGUAGE_LABELS } from "@/shared/i18n/languages";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./select";

type LanguageSwitcherProps = {
  className?: string;
};

export const LanguageSwitcher = ({ className }: LanguageSwitcherProps) => {
  const { i18n } = useTranslation();

  // Nothing to switch between when a single locale is bundled.
  if (BUNDLED_LANGS.length <= 1) return null;

  const current = BUNDLED_LANGS.includes(i18n.language)
    ? i18n.language
    : BUNDLED_LANGS[0];

  const handleChange = (lang: string) => {
    i18n.changeLanguage(lang);
  };

  return (
    <Select value={current} onValueChange={handleChange}>
      <SelectTrigger className={className}>
        <div className="flex items-center gap-2">
          <Languages className="h-4 w-4" />
          <SelectValue />
        </div>
      </SelectTrigger>
      <SelectContent>
        {BUNDLED_LANGS.map((lang) => (
          <SelectItem key={lang} value={lang}>
            {LANGUAGE_LABELS[lang] ?? lang}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};
