import { Loader2, Plus } from "lucide-react";
import { useLocation, useNavigate, useOutlet, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { Button } from "@/shared/ui/button";
import {
  useCreateWorkflowMutation,
  useGetWorkflowsQuery,
} from "@/entities/workflow";
import { selectCurrentProjectId } from "@/entities/organization";
import { useGetBillingUsageQuery } from "@/entities/billing";
import { useOnboarding } from "@/features/onboarding-v2";
import { toast } from "sonner";
import { cn } from "@/shared/lib/utils";

export const HomePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const outlet = useOutlet();
  const { projectId } = useParams();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const [createWorkflow, { isLoading: isCreating }] =
    useCreateWorkflowMutation();
  const { t } = useTranslation();
  const { isNewUser, startCanvasTour, completeWelcome } = useOnboarding();

  // Получаем список агентов для проверки, нужна ли пульсация
  const { data: workflows = [] } = useGetWorkflowsQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );

  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });

  const showPulse = workflows.length === 0;

  // Проверка лимита агентов
  const agentsLimit = billingUsage?.usage.agents.limit;
  const agentsCurrent = billingUsage?.usage.agents.current ?? 0;
  const isAgentsLimitReached =
    agentsLimit !== null &&
    agentsLimit !== undefined &&
    agentsCurrent >= agentsLimit;

  // Проверка баланса кредитов
  const creditsBalance = billingUsage?.credits?.creditsBalance ?? 0;
  const isCreditsInsufficient = creditsBalance < 1;

  const handleCreateWorkflow = async () => {
    if (!currentProjectId) {
      toast.error(t("agents.selectProject"));
      return;
    }

    // Проверка лимита агентов
    if (isAgentsLimitReached) {
      toast.error(t("billing.errors.agentsLimitReached"), {
        action: {
          label: t("billing.upgrade"),
          onClick: () => navigate("/pricing"),
        },
      });
      return;
    }

    // Проверка баланса кредитов
    if (isCreditsInsufficient) {
      toast.error(t("billing.errors.creditsInsufficient"), {
        description: t("billing.errors.creditsInsfficientHint"),
        action: {
          label: t("billing.upgrade"),
          onClick: () => navigate("/pricing"),
        },
      });
      return;
    }

    try {
      const workflow = await createWorkflow({
        projectId: currentProjectId,
      }).unwrap();
      navigate(`/projects/${projectId}/workflows/${workflow.id}`);

      // Для нового пользователя помечаем приветствие просмотренным и запускаем тур
      if (isNewUser) {
        await completeWelcome();
        startCanvasTour();
      }
    } catch (error) {
      console.error(error);
      // Обработка ошибки 402 (лимит достигнут на бэкенде)
      if (
        error &&
        typeof error === "object" &&
        "status" in error &&
        error.status === 402
      ) {
        const errorData = error as {
          status: number;
          data?: { detail?: string };
        };
        toast.error(
          errorData.data?.detail || t("billing.errors.limitReached"),
          {
            action: {
              label: t("billing.upgrade"),
              onClick: () => navigate("/pricing"),
            },
          }
        );
      } else {
        toast.error(t("agents.createError"));
      }
    }
  };

  return (
    <div className="min-h-full">
      <main className="container mx-auto px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl space-y-8">
          <div className="flex flex-col items-center space-y-6 py-8 text-center">
            <div className="space-y-2">
              <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                {t("home.title")}
              </h2>
              <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
                {t("home.subtitle")}
              </p>
            </div>
            <div className="flex flex-col items-center gap-3">
              <Button
                onClick={handleCreateWorkflow}
                disabled={
                  isCreating || isAgentsLimitReached || isCreditsInsufficient
                }
                size="lg"
                className={cn(
                  "h-12 rounded-full px-8 text-base",
                  showPulse &&
                    !isAgentsLimitReached &&
                    !isCreditsInsufficient &&
                    "animate-pulse-glow"
                )}
                data-tour="create-agent"
              >
                {isCreating ? (
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                ) : (
                  <Plus className="mr-2 h-5 w-5" />
                )}
                {t("home.createAgent")}
              </Button>
              {isAgentsLimitReached && (
                <p className="text-sm text-muted-foreground">
                  {t("billing.errors.agentsLimitReachedHint")}{" "}
                  <button
                    onClick={() => navigate("/pricing")}
                    className="font-medium text-primary hover:underline"
                  >
                    {t("billing.upgradePlan")}
                  </button>
                </p>
              )}
              {isCreditsInsufficient && !isAgentsLimitReached && (
                <p className="text-sm text-muted-foreground">
                  {t("billing.errors.creditsInsfficientHint")}{" "}
                  <button
                    onClick={() => navigate("/pricing")}
                    className="font-medium text-primary hover:underline"
                  >
                    {t("billing.upgradePlan")}
                  </button>
                </p>
              )}
            </div>
          </div>

          {/* Здесь будут рендериться дочерние роуты */}
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
            >
              {outlet}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
};
