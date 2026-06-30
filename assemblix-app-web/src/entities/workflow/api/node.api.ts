import { baseApi } from "@/shared/api/baseApi";
import type { NodeDescriptor } from "../model/types";

export const nodeApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getNodes: build.query<NodeDescriptor[], void>({
      query: () => ({ url: "/nodes" }),
      providesTags: ["Nodes"],
    }),
  }),
});

export const { useGetNodesQuery } = nodeApi;
