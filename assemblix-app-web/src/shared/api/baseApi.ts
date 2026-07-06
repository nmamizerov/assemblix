import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { RootState } from "@/app/store/store";

export const baseApi = createApi({
  reducerPath: "baseApi",
  baseQuery: fetchBaseQuery({
    baseUrl: "/api",
    prepareHeaders: (headers, { getState }) => {
      const token = localStorage.getItem("accessToken");
      const currentProjectId = (getState() as RootState).workspace.currentProjectId;
      const language = localStorage.getItem("i18nextLng") || "en";

      if (token) {
        headers.set("authorization", `Bearer ${token}`);
      }

      if (currentProjectId) {
        headers.set("x-project-id", currentProjectId);
      }

      headers.set("Accept-Language", language);

      // Выводим все headers для отладки
      const allHeaders: Record<string, string> = {};
      headers.forEach((value, key) => {
        allHeaders[key] = value;
      });

      return headers;
    },
  }),
  tagTypes: [
    "Workflows",
    "Credentials",
    "ChatSessions",
    "ApiKeys",
    "Executions",
    "Organizations",
    "Projects",
    "ClientSessions",
    "Billing",
    "NodeTemplates",
    "KnowledgeBases",
    "KBDocuments",
    "LLMProviders",
    "VoiceModels",
    "NotificationChannels",
    "Nodes",
    "Config",
  ],
  endpoints: () => ({}),
});
