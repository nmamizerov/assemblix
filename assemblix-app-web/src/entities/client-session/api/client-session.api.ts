import { baseApi } from "@/shared/api/baseApi";
import type { PaginationResponse } from "@/shared/model";
import type { ClientSession, UpdateMetadataRequest } from "../model/types";
import type { ExecutionListItem } from "@/entities/execution/model/types";
import type { ChatSession } from "@/entities/chat-session/model/types";

export interface ClientSessionsQueryParams {
  projectId: string;
  page?: number;
  limit?: number;
  activeOnly?: boolean;
  includeDebug?: boolean;
}

export interface ClientSessionExecutionsParams {
  projectId: string;
  clientId: string;
  page?: number;
  limit?: number;
}

export interface ClientSessionChatSessionsParams {
  projectId: string;
  clientId: string;
  page?: number;
  limit?: number;
}

export const clientSessionApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getClientSessions: build.query<
      PaginationResponse<ClientSession>,
      ClientSessionsQueryParams
    >({
      query: ({ projectId, page = 1, limit = 50, activeOnly = false, includeDebug = false }) => ({
        url: `/projects/${projectId}/client-sessions`,
        method: "GET",
        params: {
          page,
          limit,
          active_only: activeOnly,
          include_debug: includeDebug,
        },
      }),
      providesTags: ["ClientSessions"],
    }),
    getClientSession: build.query<
      ClientSession,
      { projectId: string; clientId: string }
    >({
      query: ({ projectId, clientId }) => ({
        url: `/projects/${projectId}/client-sessions/${clientId}`,
        method: "GET",
      }),
      providesTags: (_result, _error, { clientId }) => [
        { type: "ClientSessions", id: clientId },
      ],
    }),
    getClientSessionExecutions: build.query<
      PaginationResponse<ExecutionListItem>,
      ClientSessionExecutionsParams
    >({
      query: ({ projectId, clientId, page = 1, limit = 50 }) => ({
        url: `/projects/${projectId}/client-sessions/${clientId}/executions`,
        method: "GET",
        params: { page, limit },
      }),
      providesTags: (_result, _error, { clientId }) => [
        { type: "ClientSessions", id: `${clientId}-executions` },
      ],
    }),
    getClientSessionChatSessions: build.query<
      PaginationResponse<ChatSession>,
      ClientSessionChatSessionsParams
    >({
      query: ({ projectId, clientId, page = 1, limit = 50 }) => ({
        url: `/projects/${projectId}/client-sessions/${clientId}/chat-sessions`,
        method: "GET",
        params: { page, limit },
      }),
      providesTags: (_result, _error, { clientId }) => [
        { type: "ClientSessions", id: `${clientId}-chats` },
      ],
    }),
    updateClientSessionMetadata: build.mutation<
      ClientSession,
      {
        projectId: string;
        clientId: string;
        data: UpdateMetadataRequest;
      }
    >({
      query: ({ projectId, clientId, data }) => ({
        url: `/projects/${projectId}/client-sessions/${clientId}/metadata`,
        method: "PATCH",
        body: data,
      }),
      invalidatesTags: (_result, _error, { clientId }) => [
        { type: "ClientSessions", id: clientId },
        "ClientSessions",
      ],
    }),
    deactivateClientSession: build.mutation<
      void,
      { projectId: string; clientId: string }
    >({
      query: ({ projectId, clientId }) => ({
        url: `/projects/${projectId}/client-sessions/${clientId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["ClientSessions"],
    }),
  }),
});

export const {
  useGetClientSessionsQuery,
  useGetClientSessionQuery,
  useGetClientSessionExecutionsQuery,
  useGetClientSessionChatSessionsQuery,
  useUpdateClientSessionMetadataMutation,
  useDeactivateClientSessionMutation,
} = clientSessionApi;
