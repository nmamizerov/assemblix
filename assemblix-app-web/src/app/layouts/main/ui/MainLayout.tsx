import { useEffect, useMemo } from "react";
import { useNavigate, useOutlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useMeQuery, selectIsAuthorized } from "@/entities/session";
import { useSelector } from "react-redux";
import { Loader2 } from "lucide-react";
import { CredentialsModal } from "@/entities/credential";
import { Header } from "@/shared/ui/header";
import { Sidebar } from "@/shared/ui/sidebar";
import { AppFooter } from "@/shared/ui/app-footer";

export const MainLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const outlet = useOutlet();
  const isAuthorized = useSelector(selectIsAuthorized);

  // Создаем ключ для анимации, который не меняется при переключении между /workflows, /chats и /executions
  // так как в HomePage есть своя анимация для этих переходов
  const animationKey = useMemo(() => {
    const path = location.pathname;
    // Если это /workflows, /chats или /executions, используем общий ключ "home"
    // чтобы избежать двойной анимации с HomePage
    if (path.match(/^\/projects\/[^/]+\/workflows$/) || path === "/workflows" || path === "/chats" || path === "/executions") {
      return "home";
    }
    // Для всех остальных роутов используем полный путь
    return path;
  }, [location.pathname]);

  // Определяем, нужно ли показывать Header и Sidebar (скрываем только на странице canvas и execution viewer)
  const shouldShowHeaderAndSidebar = useMemo(() => {
    const path = location.pathname;
    // Скрываем Header и Sidebar на:
    // 1. Странице canvas (workflow details): /workflows/:id
    // 2. Странице execution viewer: /workflows/:id/executions/:id
    return !path.match(/^\/projects\/[^/]+\/workflows\/[^/]+(\/executions\/[^/]+)?$/);
  }, [location.pathname]);

  // Skip fetching if not authorized initially to avoid unnecessary requests
  // but if we have a token, we want to verify it
  const { isLoading, isError } = useMeQuery(undefined, {
    skip: !isAuthorized,
  });

  useEffect(() => {
    if (!isAuthorized) {
      navigate("/auth/login");
    } else if (isError) {
      // logic for clearing token is handled in slice middleware/matcher
      // here we just ensure navigation happens
      // However, since slice clears auth on 401, isAuthorized becomes false,
      // triggering the first condition.
      // But if isError is true (e.g. network error) we might not want to redirect immediately unless it's 401.
      // The slice handles 401 specifically.
    }
  }, [isAuthorized, isError, navigate]);

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  // If we are here and not authorized, useEffect will redirect.
  // We can return null or a loader to prevent flash of content.
  if (!isAuthorized) {
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col bg-sidebar">
      <AnimatePresence>
        {shouldShowHeaderAndSidebar && (
          <motion.div
            key="header"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.1, ease: "easeInOut" }}
          >
            <Header />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-1 overflow-hidden">
        <AnimatePresence>
          {shouldShowHeaderAndSidebar && (
            <motion.div
              key="sidebar"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.1, ease: "easeInOut" }}
            >
              <Sidebar />
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence mode="wait">
          <motion.main
            key={animationKey}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1, ease: "easeInOut" }}
            className="flex-1 overflow-auto"
          >
            {shouldShowHeaderAndSidebar ? (
              <div className="h-full p-3">
                <div className="h-full bg-card rounded-2xl p-10 overflow-auto">
                  {outlet}
                </div>
              </div>
            ) : (
              outlet
            )}
          </motion.main>
        </AnimatePresence>
      </div>

      {shouldShowHeaderAndSidebar && <AppFooter />}
      <CredentialsModal />
    </div>
  );
};
