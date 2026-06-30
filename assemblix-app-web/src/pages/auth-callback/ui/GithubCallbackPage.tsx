import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useDispatch } from "react-redux";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useGithubOAuthMutation } from "@/entities/session";
import { clearWorkspace } from "@/entities/organization";
import { baseApi } from "@/shared/api";

const GITHUB_STATE_KEY = "githubOAuthState";

type ValidationResult =
  | { kind: "ok"; code: string }
  | { kind: "error"; message: string };

export const GithubCallbackPage = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [githubOAuth] = useGithubOAuthMutation();
  const [asyncError, setAsyncError] = useState<string | null>(null);
  const hasRunRef = useRef(false);

  // Synchronous validation derived from URL — runs once and is stable.
  // Reading sessionStorage inside useMemo with [] deps reflects its value at first render.
  const validation = useMemo<ValidationResult>(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const expectedState = sessionStorage.getItem(GITHUB_STATE_KEY);

    const oauthError = searchParams.get("error");
    if (oauthError) {
      return {
        kind: "error",
        message:
          searchParams.get("error_description") ||
          t("auth.oauth.githubErrorDescription"),
      };
    }
    if (!code) {
      return { kind: "error", message: t("auth.oauth.githubErrorDescription") };
    }
    if (!expectedState || expectedState !== state) {
      return { kind: "error", message: t("auth.oauth.githubStateMismatch") };
    }
    return { kind: "ok", code };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (hasRunRef.current) return;
    hasRunRef.current = true;

    // Clear state token regardless of outcome.
    sessionStorage.removeItem(GITHUB_STATE_KEY);

    if (validation.kind === "error") {
      toast.error(t("auth.oauth.githubError"), {
        description: validation.message,
      });
      return;
    }

    (async () => {
      try {
        dispatch(clearWorkspace());
        dispatch(baseApi.util.resetApiState());

        await githubOAuth({ idToken: validation.code }).unwrap();
        navigate("/");
      } catch (error: unknown) {
        console.error("GitHub OAuth error:", error);

        const errorStatus =
          error && typeof error === "object" && "status" in error
            ? (error as { status: number }).status
            : null;

        if (errorStatus === 409) {
          const description = t("auth.oauth.emailAlreadyRegisteredDescription");
          setAsyncError(description);
          toast.error(t("auth.oauth.emailAlreadyRegistered"), { description });
        } else {
          const description = t("auth.oauth.githubErrorDescription");
          setAsyncError(description);
          toast.error(t("auth.oauth.githubError"), { description });
        }
      }
    })();
  }, [validation, githubOAuth, dispatch, navigate, t]);

  const displayedError =
    asyncError ?? (validation.kind === "error" ? validation.message : null);

  if (displayedError) {
    return (
      <div className="flex flex-col items-center text-center space-y-4">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {t("auth.oauth.githubError")}
        </h1>
        <p className="text-sm text-muted-foreground">{displayedError}</p>
        <Link
          to="/auth/login"
          className="text-sm font-medium text-primary hover:underline underline-offset-4"
        >
          {t("auth.login")}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center text-center space-y-4">
      <Loader2 className="w-8 h-8 animate-spin text-primary" />
      <p className="text-sm text-muted-foreground">
        {t("auth.oauth.githubProcessing")}
      </p>
    </div>
  );
};
