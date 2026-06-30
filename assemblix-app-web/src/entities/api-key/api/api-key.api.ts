import { baseApi } from "@/shared/api/baseApi";
import type {
  ApiKey,
  ApiKeyWithSecret,
  CreateApiKeyRequest,
  GetApiKeysResponse,
} from "../model/types";

interface GetApiKeysParams {
  projectId: string;
}

export const apiKeyApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getApiKeys: build.query<GetApiKeysResponse, GetApiKeysParams>({
      query: ({ projectId }) => ({
        url: "/api-keys/",
        method: "GET",
        params: { project_id: projectId },
      }),
      providesTags: (result) =>
        result
          ? [
            ...result.keys.map(({ id }) => ({
              type: "ApiKeys" as const,
              id,
            })),
            { type: "ApiKeys", id: "LIST" },
          ]
          : [{ type: "ApiKeys", id: "LIST" }],
    }),
    getApiKeyById: build.query<ApiKey, string>({
      query: (id) => ({
        url: `/api-keys/${id}/`,
        method: "GET",
      }),
      providesTags: (_result, _error, id) => [{ type: "ApiKeys", id }],
    }),
    createApiKey: build.mutation<
      ApiKeyWithSecret,
      CreateApiKeyRequest & { projectId: string }
    >({
      query: ({ projectId, ...body }) => ({
        url: "/api-keys/",
        method: "POST",
        body: { ...body, project_id: projectId },
      }),
      invalidatesTags: [{ type: "ApiKeys", id: "LIST" }],
    }),
    deleteApiKey: build.mutation<void, string>({
      query: (id) => ({
        url: `/api-keys/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, id) => [
        { type: "ApiKeys", id },
        { type: "ApiKeys", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetApiKeysQuery,
  useGetApiKeyByIdQuery,
  useCreateApiKeyMutation,
  useDeleteApiKeyMutation,
} = apiKeyApi;
