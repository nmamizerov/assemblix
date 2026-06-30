import { baseApi } from "@/shared/api/baseApi";
import type { PaginationResponse } from "@/shared/model";
import type { ChatSession, ChatSessionDetail } from "../model/types";

export interface ChatSessionsQueryParams {
  projectId: string;
  page?: number;
  limit?: number;
  includeDebug?: boolean;
  workflowId?: string;
}

export const chatSessionApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getChatSessions: build.query<
      PaginationResponse<ChatSession>,
      ChatSessionsQueryParams
    >({
      query: ({ projectId, page = 1, limit = 10, includeDebug = false, workflowId }) => ({
        url: "chat-sessions/",
        method: "GET",
        params: { 
          project_id: projectId, 
          page, 
          limit, 
          ...(workflowId && { workflow_id: workflowId }),
          include_debug: includeDebug 
        },
      }),
      providesTags: ["ChatSessions"],
    }),
    getChatSessionDetail: build.query<ChatSessionDetail, string>({
      query: (id) => ({
        url: `chat-sessions/${id}`,
        method: "GET",
      }),
      providesTags: (result) => [{ type: "ChatSessions", id: result?.id }],
    }),
    renameChatSession: build.mutation<ChatSessionDetail, { id: string; name: string }>({
      query: ({ id, name }) => ({
        url: `chat-sessions/${id}/name`,
        method: "PATCH",
        body: { name },
      }),
      invalidatesTags: ["ChatSessions"],
    }),
    deleteChatSession: build.mutation<void, string>({
      query: (id) => ({
        url: `chat-sessions/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["ChatSessions"],
    }),
  }),
});

export const {
  useGetChatSessionsQuery,
  useGetChatSessionDetailQuery,
  useRenameChatSessionMutation,
  useDeleteChatSessionMutation,
} = chatSessionApi;
