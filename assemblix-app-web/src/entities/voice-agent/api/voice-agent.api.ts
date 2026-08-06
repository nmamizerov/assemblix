import { baseApi } from "@/shared/api/baseApi";
import type {
  CreateVoiceAgentRequest,
  UpdateVoiceAgentRequest,
  VoiceAgent,
} from "../model/types";

interface GetVoiceAgentsParams {
  projectId: string;
}

export const voiceAgentApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getVoiceAgents: build.query<VoiceAgent[], GetVoiceAgentsParams>({
      query: ({ projectId }) => ({
        url: "/voice-agents/",
        method: "GET",
        params: { project_id: projectId },
      }),
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ id }) => ({ type: "VoiceAgents" as const, id })),
              { type: "VoiceAgents", id: "LIST" },
            ]
          : [{ type: "VoiceAgents", id: "LIST" }],
    }),

    getVoiceAgent: build.query<VoiceAgent, string>({
      query: (id) => ({ url: `/voice-agents/${id}`, method: "GET" }),
      providesTags: (_result, _error, id) => [{ type: "VoiceAgents", id }],
    }),

    createVoiceAgent: build.mutation<VoiceAgent, CreateVoiceAgentRequest>({
      query: (body) => ({ url: "/voice-agents/", method: "POST", body }),
      invalidatesTags: [{ type: "VoiceAgents", id: "LIST" }],
    }),

    updateVoiceAgent: build.mutation<VoiceAgent, UpdateVoiceAgentRequest>({
      query: ({ id, ...patch }) => ({
        url: `/voice-agents/${id}`,
        method: "PATCH",
        body: patch,
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: "VoiceAgents", id },
        { type: "VoiceAgents", id: "LIST" },
      ],
    }),

    deleteVoiceAgent: build.mutation<void, string>({
      query: (id) => ({ url: `/voice-agents/${id}`, method: "DELETE" }),
      invalidatesTags: [{ type: "VoiceAgents", id: "LIST" }],
    }),
  }),
});

export const {
  useGetVoiceAgentsQuery,
  useGetVoiceAgentQuery,
  useCreateVoiceAgentMutation,
  useUpdateVoiceAgentMutation,
  useDeleteVoiceAgentMutation,
} = voiceAgentApi;
