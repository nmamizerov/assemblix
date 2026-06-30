import { Outlet, Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AppFooter } from "@/shared/ui/app-footer";

export const AuthLayout = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const isLogin = location.pathname === "/auth/login";

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Хедер с логотипом */}
      <header className="p-6">
        <Link to="/" className="flex items-center text-lg font-semibold">
          <img src="/logo.svg" alt="Assemblix" className="mr-2 h-8 w-8" />
          Assemblix
        </Link>
      </header>

      {/* Форма по центру */}
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">
          <div className="border border-border bg-card rounded-lg shadow-lg p-6 space-y-6">
            <Outlet />

            {/* Ссылка переключения */}
            <div className="pt-4 text-center text-sm text-muted-foreground border-t border-border">
              <p className="pt-4">
                {isLogin ? t("auth.noAccount") : t("auth.hasAccount")}{" "}
                <Link
                  to={isLogin ? "/auth/register" : "/auth/login"}
                  className="text-primary hover:text-primary/80 font-medium transition-colors underline-offset-4 hover:underline"
                >
                  {isLogin ? t("auth.signUp") : t("auth.signIn")}
                </Link>
              </p>
            </div>
          </div>
        </div>
      </main>
      <AppFooter />
    </div>
  );
};
