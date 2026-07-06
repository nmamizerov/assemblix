import { baseApi } from "@/shared/api/baseApi";
import type {
  VoiceCapability,
  VoiceListItem,
  VoiceModelMetadata,
  VoiceProviderListItem,
} from "../model/types";

interface GetVoiceProvidersParams {
  capability?: VoiceCapability;
}

interface GetVoiceModelsParams {
  providerName: string;
  capability?: VoiceCapability;
}

interface GetCredentialVoicesParams {
  credentialId: string;
}

export const voiceModelApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getVoiceProviders: build.query<VoiceProviderListItem[], GetVoiceProvidersParams | void>({
      query: (arg) => ({
        url: "/voice/providers",
        method: "GET",
        params: arg?.capability ? { capability: arg.capability } : undefined,
      }),
      providesTags: (_result, _error, arg) => [
        { type: "VoiceModels", id: arg?.capability ? `LIST:${arg.capability}` : "LIST" },
      ],
    }),

    getVoiceProviderModels: build.query<VoiceModelMetadata[], GetVoiceModelsParams>({
      query: ({ providerName, capability }) => ({
        url: `/voice/providers/${providerName}/models`,
        method: "GET",
        params: capability ? { capability } : undefined,
      }),
      providesTags: (_result, _error, { providerName, capability }) => [
        {
          type: "VoiceModels",
          id: `models:${providerName}${capability ? `:${capability}` : ""}`,
        },
      ],
    }),

    getCredentialVoices: build.query<VoiceListItem[], GetCredentialVoicesParams>({
      query: ({ credentialId }) => ({
        url: `/voice/credentials/${credentialId}/voices`,
        method: "GET",
      }),
      providesTags: (_result, _error, { credentialId }) => [
        { type: "VoiceModels", id: `voices:${credentialId}` },
      ],
    }),
  }),
});

export const {
  useGetVoiceProvidersQuery,
  useGetVoiceProviderModelsQuery,
  useGetCredentialVoicesQuery,
} = voiceModelApi;
