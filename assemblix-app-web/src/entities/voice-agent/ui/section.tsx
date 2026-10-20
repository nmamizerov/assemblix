import { useTranslation } from "react-i18next";

interface SectionProps {
  title: string;
  hint: string;
  children: React.ReactNode;
}

/**
 * Section label and its one-line purpose sit in a narrow rail beside the fields.
 * Two effects: the eye gets a stable left edge to scan, and inputs stop
 * stretching to the full width of the page, which is what made this read as a
 * settings dump rather than a considered form.
 */
export const Section = ({ title, hint, children }: SectionProps) => (
  <section className="grid gap-x-10 gap-y-4 py-8 first:pt-0 last:pb-0 lg:grid-cols-[13rem_minmax(0,1fr)]">
    <div className="lg:pt-1">
      <h2 className="text-sm font-medium tracking-tight text-foreground">{title}</h2>
      <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
        {hint}
      </p>
    </div>
    <div className="max-w-2xl space-y-4">{children}</div>
  </section>
);

/** An i18n error key rendered under its field. */
export const FieldError = ({ error }: { error?: string }) => {
  const { t } = useTranslation();
  if (!error) return null;
  return <p className="text-xs text-destructive">{t(error)}</p>;
};
