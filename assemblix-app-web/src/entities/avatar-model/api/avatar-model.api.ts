import { baseApi } from "@/shared/api/baseApi";
import type {
  AvatarListItem,
  AvatarModelMetadata,
  AvatarProviderListItem,
  AvatarSessionResponse,
} from "../model/types";

export const avatarModelApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getAvatarProviders: build.query<AvatarProviderListItem[], void>({
      query: () => ({ url: "/avatar/providers", method: "GET" }),
      providesTags: [{ type: "AvatarModels", id: "LIST" }],
    }),
    getAvatarProviderModels: build.query<AvatarModelMetadata[], { providerName: string }>({
      query: ({ providerName }) => ({
        url: `/avatar/providers/${providerName}/models`,
        method: "GET",
      }),
      providesTags: (_r, _e, { providerName }) => [
        { type: "AvatarModels", id: `models:${providerName}` },
      ],
    }),
    getCredentialAvatars: build.query<AvatarListItem[], { credentialId: string }>({
      query: ({ credentialId }) => ({
        url: `/avatar/credentials/${credentialId}/avatars`,
        method: "GET",
      }),
      providesTags: (_r, _e, { credentialId }) => [
        { type: "AvatarModels", id: `avatars:${credentialId}` },
      ],
    }),
    getCredentialVoices: build.query<AvatarListItem[], { credentialId: string }>({
      query: ({ credentialId }) => ({
        url: `/avatar/credentials/${credentialId}/voices`,
        method: "GET",
      }),
      providesTags: (_r, _e, { credentialId }) => [
        { type: "AvatarModels", id: `voices:${credentialId}` },
      ],
    }),
    mintAvatarSession: build.mutation<AvatarSessionResponse, { workflowId: string }>({
      query: ({ workflowId }) => ({
        url: `/workflows/${workflowId}/avatar/session`,
        method: "POST",
      }),
    }),
  }),
});

export const {
  useGetAvatarProvidersQuery,
  useGetAvatarProviderModelsQuery,
  useGetCredentialAvatarsQuery,
  useGetCredentialVoicesQuery,
  useMintAvatarSessionMutation,
} = avatarModelApi;
