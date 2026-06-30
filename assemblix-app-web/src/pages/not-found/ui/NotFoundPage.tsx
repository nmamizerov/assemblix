import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Home, ArrowLeft } from "lucide-react";
import { Button } from "@/shared/ui/button";

/**
 * On-brand 404: a workflow path whose edge dashes off and dead-ends into a
 * disconnected node handle — "you've reached a dead end". Rendered standalone
 * (full screen) so it works for any unmatched route, authed or not.
 */
const DeadEndGraph = () => (
  <svg
    width="280"
    height="96"
    viewBox="0 0 280 96"
    fill="none"
    className="text-primary"
    aria-hidden
  >
    {/* solid edge: node 1 → node 2 */}
    <path
      d="M84 48 H108"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    />
    {/* node 1 */}
    <rect
      x="20"
      y="32"
      width="64"
      height="32"
      rx="9"
      className="fill-primary/10 stroke-primary/50"
      strokeWidth="1.5"
    />
    <circle cx="20" cy="48" r="3" className="fill-primary" />
    <circle cx="84" cy="48" r="3" className="fill-primary" />
    {/* node 2 */}
    <rect
      x="108"
      y="32"
      width="64"
      height="32"
      rx="9"
      className="fill-primary/10 stroke-primary/50"
      strokeWidth="1.5"
    />
    <circle cx="172" cy="48" r="3" className="fill-primary" />
    {/* broken, dashed edge that flows off toward nothing */}
    <motion.path
      d="M172 48 H236"
      className="text-muted-foreground"
      stroke="currentColor"
      strokeWidth="2"
      strokeDasharray="6 7"
      strokeLinecap="round"
      animate={{ strokeDashoffset: [0, -26] }}
      transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
    />
    {/* dangling, disconnected handle — the path leads nowhere */}
    <circle
      cx="244"
      cy="48"
      r="7"
      className="fill-background stroke-muted-foreground/60"
      strokeWidth="2"
      strokeDasharray="3 3"
    />
  </svg>
);

export const NotFoundPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="relative flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-background px-6 py-16 text-center">
      {/* React-Flow-style dot grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 text-foreground/[0.07]"
        style={{
          backgroundImage:
            "radial-gradient(currentColor 1.25px, transparent 1.25px)",
          backgroundSize: "24px 24px",
        }}
      />
      {/* soft glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/2 h-[36rem] w-[36rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/10 blur-[100px]"
      />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative z-10 flex max-w-md flex-col items-center"
      >
        <DeadEndGraph />

        <div className="mt-2 select-none bg-gradient-to-b from-foreground to-foreground/40 bg-clip-text text-8xl font-extrabold tracking-tighter text-transparent">
          404
        </div>

        <h1 className="mt-4 text-xl font-semibold text-foreground">
          {t("notFoundPage.title")}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {t("notFoundPage.subtitle")}
        </p>

        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
          <Button onClick={() => navigate("/")} className="gap-2">
            <Home className="size-4" />
            {t("notFoundPage.home")}
          </Button>
          <Button
            variant="ghost"
            onClick={() => navigate(-1)}
            className="gap-2"
          >
            <ArrowLeft className="size-4" />
            {t("notFoundPage.back")}
          </Button>
        </div>
      </motion.div>
    </div>
  );
};
