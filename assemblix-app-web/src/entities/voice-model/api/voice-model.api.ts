import { baseApi } from "@/shared/api/baseApi";
import type { VoiceModelMetadata, VoiceProviderListItem } from "../model/types";

interface GetVoiceModelsParams {
  providerName: string;
}

export const voiceModelApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getVoiceProviders: build.query<VoiceProviderListItem[], void>({
      query: () => ({
        url: "/voice/providers",
        method: "GET",
      }),
      providesTags: [{ type: "VoiceModels", id: "LIST" }],
    }),

    getVoiceProviderModels: build.query<VoiceModelMetadata[], GetVoiceModelsParams>({
      query: ({ providerName }) => ({
        url: `/voice/providers/${providerName}/models`,
        method: "GET",
      }),
      providesTags: (_result, _error, { providerName }) => [
        { type: "VoiceModels", id: `models:${providerName}` },
      ],
    }),
  }),
});

export const { useGetVoiceProvidersQuery, useGetVoiceProviderModelsQuery } = voiceModelApi;
