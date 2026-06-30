import { baseApi } from "@/shared/api/baseApi";

import type { ServerConfig } from "../model/types";

export const configApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /**
     * `GET /api/config` — server settings (system-key presence per provider,
     * feature flags). Cached as a single LIST entry; rarely changes at runtime.
     */
    getServerConfig: build.query<ServerConfig, void>({
      query: () => ({
        url: "/config",
        method: "GET",
      }),
      providesTags: [{ type: "Config", id: "LIST" }],
    }),
  }),
});

export const { useGetServerConfigQuery } = configApi;
