import { baseApi } from "@/shared/api/baseApi";
import type {
  ModelMetadata,
  ProviderListItem,
  ProviderSchema,
} from "../model/types";

interface GetProviderModelsParams {
  providerName: string;
}

interface GetProviderSchemaParams {
  providerName: string;
  /** Optional model id — if provided, the backend pre-filters the schema. */
  model?: string;
}

export const llmProviderApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /**
     * `GET /api/llm/providers` — list all registered providers.
     * Cached as a single LIST entry; rarely changes at runtime.
     */
    getLLMProviders: build.query<ProviderListItem[], void>({
      query: () => ({
        url: "/llm/providers",
        method: "GET",
      }),
      providesTags: [{ type: "LLMProviders", id: "LIST" }],
    }),

    /**
     * `GET /api/llm/providers/{name}/models` — model registry for one provider.
     */
    getLLMProviderModels: build.query<ModelMetadata[], GetProviderModelsParams>({
      query: ({ providerName }) => ({
        url: `/llm/providers/${providerName}/models`,
        method: "GET",
      }),
      providesTags: (_result, _error, { providerName }) => [
        { type: "LLMProviders", id: `models:${providerName}` },
      ],
    }),

    /**
     * `GET /api/llm/providers/{name}/schema?model={id}` — declarative form
     * schema for the dynamic agent-node renderer. With `model` set, the
     * server applies `show`/`hide` rules and returns only visible params.
     */
    getLLMProviderSchema: build.query<ProviderSchema, GetProviderSchemaParams>({
      query: ({ providerName, model }) => ({
        url: `/llm/providers/${providerName}/schema`,
        method: "GET",
        params: model ? { model } : undefined,
      }),
      providesTags: (_result, _error, { providerName, model }) => [
        {
          type: "LLMProviders",
          id: `schema:${providerName}${model ? `:${model}` : ""}`,
        },
      ],
    }),
  }),
});

export const {
  useGetLLMProvidersQuery,
  useGetLLMProviderModelsQuery,
  useGetLLMProviderSchemaQuery,
} = llmProviderApi;
