import { useTranslation } from "react-i18next";
import { isBillingEnabled } from "@/shared/config";

const LANDING_URL = "https://assmblx.com";

export const AppFooter = () => {
  const { t } = useTranslation();

  return (
    <footer className="py-4 px-6 text-xs text-muted-foreground flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
      <span>&copy; {new Date().getFullYear()} Assemblix</span>
      {isBillingEnabled && (
        <>
          <span className="hidden sm:inline">&middot;</span>
          <a
            href={`${LANDING_URL}/terms`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            {t("footer.terms")}
          </a>
          <span className="hidden sm:inline">&middot;</span>
          <a
            href={`${LANDING_URL}/privacy`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            {t("footer.privacy")}
          </a>
          <span className="hidden sm:inline">&middot;</span>
          <a
            href={`${LANDING_URL}/refund`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            {t("footer.refund")}
          </a>
          <span className="hidden sm:inline">&middot;</span>
          <a
            href={`${LANDING_URL}/contact`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            {t("footer.contact")}
          </a>
        </>
      )}
    </footer>
  );
};
