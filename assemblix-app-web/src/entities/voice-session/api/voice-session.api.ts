import { baseApi } from "@/shared/api/baseApi";
import type { VoiceSession, VoiceSessionDetail } from "../model/types";

interface PaginatedVoiceSessions {
  data: VoiceSession[];
  total: number;
  page: number;
  limit: number;
}

interface ListParams {
  agentId: string;
  page?: number;
  limit?: number;
}

export const voiceSessionApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getVoiceSessions: build.query<PaginatedVoiceSessions, ListParams>({
      query: ({ agentId, page = 1, limit = 50 }) => ({
        url: `/voice-agents/${agentId}/sessions`,
        method: "GET",
        params: { page, limit },
      }),
      providesTags: (_result, _error, { agentId }) => [
        { type: "VoiceSessions", id: agentId },
      ],
    }),

    getVoiceSession: build.query<VoiceSessionDetail, string>({
      query: (id) => ({ url: `/voice-sessions/${id}`, method: "GET" }),
      providesTags: (_result, _error, id) => [{ type: "VoiceSessions", id }],
    }),
  }),
});

export const { useGetVoiceSessionsQuery, useGetVoiceSessionQuery } =
  voiceSessionApi;
