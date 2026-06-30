import { useGoogleLogin } from "@react-oauth/google";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useDispatch } from "react-redux";
import { toast } from "sonner";
import { Github } from "lucide-react";

import { useGoogleOAuthMutation } from "../api/auth.api";
import { clearWorkspace } from "@/entities/organization";
import { baseApi } from "@/shared/api";
import { Button } from "@/shared/ui/button";
import { oauthConfig } from "@/shared/config";

const GITHUB_STATE_KEY = "githubOAuthState";
const GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize";
const GITHUB_SCOPE = "read:user user:email";

const generateState = () => {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
};

const GoogleIcon = () => (
  <svg
    className="w-4 h-4"
    viewBox="0 0 24 24"
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09Z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09a6.51 6.51 0 0 1 0-4.17V7.07H2.18a11 11 0 0 0 0 9.86l3.66-2.84Z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"
    />
  </svg>
);

/**
 * Google OAuth button (authorization code flow).
 *
 * useGoogleLogin({flow: 'auth-code'}) opens a popup and returns a code; the
 * frontend sends it to the backend, which exchanges it for an id_token. This
 * component is rendered only when a Google client ID is configured — calling
 * useGoogleLogin without one initialises GSI with an empty client_id and throws.
 */
const GoogleButton = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [googleOAuth] = useGoogleOAuthMutation();
  const [isProcessing, setIsProcessing] = useState(false);

  const handleGoogleCode = async (code: string) => {
    try {
      setIsProcessing(true);
      dispatch(clearWorkspace());
      dispatch(baseApi.util.resetApiState());

      await googleOAuth({ idToken: code }).unwrap();
      navigate("/");
    } catch (error: unknown) {
      console.error("Google OAuth error:", error);

      const errorStatus =
        error && typeof error === "object" && "status" in error
          ? (error as { status: number }).status
          : null;

      if (errorStatus === 409) {
        toast.error(t("auth.oauth.emailAlreadyRegistered"), {
          description: t("auth.oauth.emailAlreadyRegisteredDescription"),
        });
      } else if (errorStatus === 400) {
        toast.error(t("auth.oauth.emailNotVerified"), {
          description: t("auth.oauth.emailNotVerifiedDescription"),
        });
      } else {
        toast.error(t("auth.oauth.googleError"), {
          description: t("auth.oauth.googleErrorDescription"),
        });
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const loginWithGoogle = useGoogleLogin({
    flow: "auth-code",
    onSuccess: ({ code }) => handleGoogleCode(code),
    onError: () => {
      toast.error(t("auth.oauth.googleError"), {
        description: t("auth.oauth.cancelled"),
      });
    },
  });

  return (
    <Button
      type="button"
      variant="outline"
      onClick={() => loginWithGoogle()}
      disabled={isProcessing}
      className="w-full h-11"
    >
      <GoogleIcon />
      <span className="ml-2">{t("auth.oauth.continueWithGoogle")}</span>
    </Button>
  );
};

/**
 * GitHub OAuth button — manual redirect to github.com, returns to
 * /auth/callback/github where the code is exchanged on the backend. Rendered
 * only when a GitHub client ID is configured.
 */
const GithubButton = () => {
  const { t } = useTranslation();

  const handleGithubClick = () => {
    const state = generateState();
    sessionStorage.setItem(GITHUB_STATE_KEY, state);

    const params = new URLSearchParams({
      client_id: oauthConfig.github.clientId,
      redirect_uri: `${window.location.origin}/auth/callback/github`,
      scope: GITHUB_SCOPE,
      state,
    });

    window.location.href = `${GITHUB_AUTHORIZE_URL}?${params.toString()}`;
  };

  return (
    <Button
      type="button"
      variant="outline"
      onClick={handleGithubClick}
      className="w-full h-11"
    >
      <Github className="w-4 h-4 mr-2" />
      {t("auth.oauth.continueWithGitHub")}
    </Button>
  );
};

/**
 * OAuth buttons block (Google, GitHub). Renders nothing when neither provider
 * is configured, so self-host builds without OAuth env vars show only the
 * email/password form.
 */
export const OAuthButtons = () => {
  const { t } = useTranslation();

  if (!oauthConfig.google.enabled && !oauthConfig.github.enabled) {
    return null;
  }

  return (
    <div className="space-y-3 mt-3">
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">
            {t("common.or")}
          </span>
        </div>
      </div>

      {oauthConfig.google.enabled && <GoogleButton />}
      {oauthConfig.github.enabled && <GithubButton />}
    </div>
  );
};
