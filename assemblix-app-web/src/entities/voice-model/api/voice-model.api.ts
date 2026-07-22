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
  search?: string;
}

interface GetSystemVoicesParams {
  providerName: string;
  search?: string;
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
      query: ({ credentialId, search }) => ({
        url: `/voice/credentials/${credentialId}/voices`,
        method: "GET",
        params: search ? { search } : undefined,
      }),
      providesTags: (_result, _error, { credentialId, search }) => [
        { type: "VoiceModels", id: `voices:${credentialId}:${search ?? ""}` },
      ],
    }),

    getSystemVoices: build.query<VoiceListItem[], GetSystemVoicesParams>({
      query: ({ providerName, search }) => ({
        url: `/voice/providers/${providerName}/system-voices`,
        method: "GET",
        params: search ? { search } : undefined,
      }),
      providesTags: (_result, _error, { providerName, search }) => [
        { type: "VoiceModels", id: `system-voices:${providerName}:${search ?? ""}` },
      ],
    }),
  }),
});

export const {
  useGetVoiceProvidersQuery,
  useGetVoiceProviderModelsQuery,
  useGetCredentialVoicesQuery,
  useGetSystemVoicesQuery,
} = voiceModelApi;
