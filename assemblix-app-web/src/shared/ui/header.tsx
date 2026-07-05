import { User, LogOut, Moon, Sun, Crown, Coins, Building2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Button } from "./button";
import { Divider } from "./divider";
import { LanguageSwitcher } from "./language-switcher";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./tooltip";
import { useMeQuery, logout, selectIsAuthorized } from "@/entities/session";
import {
  clearWorkspace,
  OrgProjectSelector,
  selectCurrentOrganizationId,
} from "@/entities/organization";
import {
  useGetBillingPlanQuery,
  useGetBillingUsageQuery,
} from "@/entities/billing";
import { useTheme } from "@/shared/lib/theme-context";
import { useFormatDate } from "@/shared/lib/format-date";
import { isBillingEnabled } from "@/shared/config";
import { useTranslation } from "react-i18next";
import { baseApi } from "@/shared/api";
import { getCommunityLinks } from "@/shared/lib/community-links";

export const Header = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const isAuthorized = useSelector(selectIsAuthorized);
  const currentOrganizationId = useSelector(selectCurrentOrganizationId);
  const { data: user } = useMeQuery(undefined, {
    skip: !isAuthorized,
  });
  const { data: billingPlan } = useGetBillingPlanQuery(
    currentOrganizationId ?? undefined,
    {
      skip: !currentOrganizationId || !isAuthorized || !isBillingEnabled,
    }
  );
  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentOrganizationId || !isAuthorized || !isBillingEnabled,
  });
  const { theme, setTheme } = useTheme();
  const { t, i18n } = useTranslation();
  const { formatNumber } = useFormatDate();
  const communityLinks = getCommunityLinks(i18n.language);

  const handleLogout = () => {
    dispatch(logout());
    dispatch(clearWorkspace());
    dispatch(baseApi.util.resetApiState());
    navigate("/auth/login");
  };

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  const showAuthButtons = !user;

  // Определяем цвет и текст кнопки в зависимости от плана
  const getPlanButtonVariant = () => {
    if (!billingPlan) return "outline";
    switch (billingPlan.plan) {
      case "free":
        return "outline";
      case "starter":
        return "default";
      case "pro":
        return "default";
      case "business":
        return "default";
      default:
        return "outline";
    }
  };

  const getPlanButtonText = () => {
    if (!billingPlan) return t("billing.upgrade");
    switch (billingPlan.plan) {
      case "free":
        return t("billing.upgrade");
      case "starter":
        return "STARTER";
      case "pro":
        return "PRO";
      case "business":
        return "BUSINESS";
      default:
        return t("billing.upgrade");
    }
  };

  return (
    <header className="sticky top-0 z-50 bg-header">
      <div className="mx-auto flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2">
            <img
              src="/logo.svg"
              alt={t("header.appName")}
              className="h-8 w-8"
            />
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              {t("header.appName")}
            </h1>
          </Link>
          {!showAuthButtons && <OrgProjectSelector />}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5"
            asChild
          >
            <a
              href={communityLinks.support}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("header.help")}
            </a>
          </Button>

          {/* Credits Balance - показываем баланс кредитов */}
          {isBillingEnabled && !showAuthButtons && billingUsage && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-sm">
                    <Coins className="h-4 w-4 text-primary" />
                    <span className="font-semibold text-foreground">
                      {formatNumber(
                        billingUsage.credits?.creditsBalance ?? 0
                      )}
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t("billing.credits.balance")}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}

          {/* Billing Button - показываем только для авторизованных пользователей */}
          {isBillingEnabled && !showAuthButtons && billingPlan && (
            <Button
              variant={getPlanButtonVariant()}
              size="sm"
              className="h-8 gap-1.5"
              onClick={() => navigate("/pricing")}
            >
              <Crown className="h-3.5 w-3.5" />
              <span className="text-xs font-semibold">
                {getPlanButtonText()}
              </span>
            </Button>
          )}

          {showAuthButtons ? (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9"
                onClick={toggleTheme}
              >
                {theme === "dark" ? (
                  <Sun className="h-4 w-4" />
                ) : (
                  <Moon className="h-4 w-4" />
                )}
              </Button>
              <Button variant="ghost" onClick={() => navigate("/auth/login")}>
                {t("auth.login")}
              </Button>
              <Button onClick={() => navigate("/auth/register")}>
                {t("auth.register")}
              </Button>
            </>
          ) : (
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 rounded-full"
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <User className="h-4 w-4" />
                  </div>
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-64 p-2">
                <div className="space-y-1">
                  {/* User Info */}
                  <div className="px-3 py-2">
                    <p className="text-sm font-medium text-foreground">
                      {user?.fullName || user?.email || t("auth.user")}
                    </p>
                    {user?.email && user?.fullName && (
                      <p className="text-xs text-muted-foreground">
                        {user.email}
                      </p>
                    )}
                  </div>

                  <Divider />

                  {/* Organization Settings */}
                  <Button
                    variant="ghost"
                    className="w-full justify-start gap-3 px-3"
                    onClick={() => navigate("/organization/settings")}
                  >
                    <Building2 className="h-4 w-4" />
                    <span>{t("header.organizationSettings")}</span>
                  </Button>

                  <Divider />

                  {/* Theme Toggle */}
                  <Button
                    variant="ghost"
                    className="w-full justify-start gap-3 px-3"
                    onClick={toggleTheme}
                  >
                    {theme === "dark" ? (
                      <>
                        <Sun className="h-4 w-4" />
                        <span>{t("header.lightTheme")}</span>
                      </>
                    ) : (
                      <>
                        <Moon className="h-4 w-4" />
                        <span>{t("header.darkTheme")}</span>
                      </>
                    )}
                  </Button>

                  <Divider />

                  {/* Language */}
                  <div className="px-3 py-1.5">
                    <LanguageSwitcher className="w-full" />
                  </div>

                  <Divider />

                  {/* Logout */}
                  <Button
                    variant="ghost"
                    className="w-full justify-start gap-3 px-3 text-destructive hover:bg-destructive/10 hover:text-destructive"
                    onClick={handleLogout}
                  >
                    <LogOut className="h-4 w-4" />
                    <span>{t("auth.logout")}</span>
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
          )}
        </div>
      </div>
    </header>
  );
};
