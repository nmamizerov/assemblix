import React from "react";
import { Provider } from "react-redux";
import { RouterProvider } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { store } from "@/app/store";
import { appRouter } from "@/app/router";
import { ThemeProvider } from "./ThemeProvider";
import { PaddleProvider } from "./PaddleProvider";
import { Toaster } from "sonner";
import i18n from "@/shared/i18n";
import { oauthConfig } from "@/shared/config";

export const Providers = () => {
  const content = (
    <I18nextProvider i18n={i18n}>
      <Provider store={store}>
        <ThemeProvider defaultTheme="light" storageKey="assemblix-theme">
          <PaddleProvider>
            <RouterProvider router={appRouter} />
            <Toaster position="top-right" />
          </PaddleProvider>
        </ThemeProvider>
      </Provider>
    </I18nextProvider>
  );

  // Only mount the Google provider when a client ID is configured — otherwise
  // its GSI script initialises with an empty client_id and crashes the app.
  return (
    <React.StrictMode>
      {oauthConfig.google.enabled ? (
        <GoogleOAuthProvider clientId={oauthConfig.google.clientId}>
          {content}
        </GoogleOAuthProvider>
      ) : (
        content
      )}
    </React.StrictMode>
  );
};
