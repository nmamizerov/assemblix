import { createBrowserRouter, Navigate } from "react-router-dom";
import { LoginPage } from "@/pages/login";
import { RegisterPage } from "@/pages/register";
import { GithubCallbackPage } from "@/pages/auth-callback";
import { HomePage } from "@/pages/home";
import { AgentsPage } from "@/pages/agents";
import { ChatDetailsPage } from "@/pages/chat-details";
import { WorkflowDetailsPage } from "@/pages/workflow-details";
import { ExecutionViewerPage } from "@/pages/execution-viewer";
import { SettingsPage } from "@/pages/settings";
import { ApiKeysPage } from "@/pages/api-keys";
import { OrganizationSettingsPage } from "@/pages/organization-settings";
import { ClientSessionsPage } from "@/pages/client-sessions";
import { ClientSessionDetailsPage } from "@/pages/client-session-details";
import {
  ProjectSettingsPage,
  ProjectSettingsLayout,
  CredentialsTab,
  NotificationsTab,
} from "@/pages/project-settings";
import { PricingPage } from "@/pages/pricing";
import { SessionsPage } from "@/pages/sessions";
import { PaymentSuccessPage } from "@/pages/payment-success";
import { KnowledgeBasesPage } from "@/pages/knowledge-bases";
import { KnowledgeBaseDetailsPage } from "@/pages/knowledge-base-details";
import { NotFoundPage } from "@/pages/not-found";
import { AuthLayout } from "@/app/layouts/auth";
import { MainLayout } from "@/app/layouts/main";
import { ProjectLayout } from "@/app/layouts/project";
import { isBillingEnabled } from "@/shared/config";
import { RootRedirect } from "./RootRedirect";
import { SettingsRedirect } from "./SettingsRedirect";

export const appRouter = createBrowserRouter([
  {
    element: <AuthLayout />,
    path: "/auth/",
    children: [
      {
        path: "login",
        element: <LoginPage />,
      },
      {
        path: "register",
        element: <RegisterPage />,
      },
      {
        path: "callback/github",
        element: <GithubCallbackPage />,
      },
    ],
  },
  {
    element: <MainLayout />,
    path: "/",
    children: [
      {
        index: true,
        element: <RootRedirect />,
      },
      {
        path: "projects/:projectId",
        element: <ProjectLayout />,
        children: [
          {
            element: <HomePage />,
            children: [
              {
                index: true,
                element: <Navigate to="workflows" replace />,
              },
              {
                path: "workflows",
                element: <AgentsPage />,
              },
            ],
          },
          {
            path: "workflows/:workflowId",
            element: <WorkflowDetailsPage />,
          },
          {
            path: "workflows/:workflowId/executions/:executionId",
            element: <ExecutionViewerPage />,
          },
          {
            path: "sessions",
            element: <SessionsPage />,
          },
          {
            path: "chats/:chatId",
            element: <ChatDetailsPage />,
          },
          {
            path: "client-sessions",
            element: <ClientSessionsPage />,
          },
          {
            path: "client-sessions/:clientId",
            element: <ClientSessionDetailsPage />,
          },
          {
            path: "knowledge-bases",
            element: <KnowledgeBasesPage />,
          },
          {
            path: "knowledge-bases/:knowledgeBaseId",
            element: <KnowledgeBaseDetailsPage />,
          },
          {
            path: "settings",
            element: <ProjectSettingsLayout />,
            children: [
              {
                index: true,
                element: <Navigate to="general" replace />,
              },
              {
                path: "general",
                element: <ProjectSettingsPage />,
              },
              {
                path: "api-keys",
                element: <ApiKeysPage />,
              },
              {
                path: "credentials",
                element: <CredentialsTab />,
              },
              {
                path: "notifications",
                element: <NotificationsTab />,
              },
            ],
          },
          {
            path: "api-keys",
            element: <SettingsRedirect to="api-keys" />,
          },
          {
            path: "project/settings",
            element: <SettingsRedirect to="general" />,
          },
        ],
      },
      // Non-project routes
      {
        path: "settings",
        element: <SettingsPage />,
      },
      {
        path: "organization/settings",
        element: <OrganizationSettingsPage />,
      },
      // Billing routes — only mounted in the commercial build
      ...(isBillingEnabled
        ? [
            {
              path: "pricing",
              element: <PricingPage />,
            },
            {
              path: "payments/success",
              element: <PaymentSuccessPage />,
            },
          ]
        : []),
      // Legacy redirects
      {
        path: "workflows",
        element: <RootRedirect />,
      },
      {
        path: "workflows/:workflowId",
        element: <RootRedirect />,
      },
      {
        path: "sessions",
        element: <RootRedirect />,
      },
      {
        path: "api-keys",
        element: <RootRedirect />,
      },
      {
        path: "knowledge-bases",
        element: <RootRedirect />,
      },
      {
        path: "client-sessions",
        element: <RootRedirect />,
      },
    ],
  },
  // Catch-all 404 for any unmatched route
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
