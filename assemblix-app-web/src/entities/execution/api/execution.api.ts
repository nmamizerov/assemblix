import { baseApi } from "@/shared/api/baseApi";
import type { PaginationResponse } from "@/shared/model";
import type {
  ExecutionDetailResponse,
  ExecutionListItem,
} from "../model/types";

export interface ExecutionsQueryParams {
  projectId: string;
  page?: number;
  limit?: number;
  clientId?: string;
  includeDebug?: boolean;
  workflowId?: string;
}

export const executionApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getExecutions: build.query<
      PaginationResponse<ExecutionListItem>,
      ExecutionsQueryParams
    >({
      query: ({ projectId, page = 1, limit = 10, clientId, includeDebug = false, workflowId }) => ({
        url: "/executions/",
        method: "GET",
        params: {
          project_id: projectId,
          page,
          limit,
          ...(clientId && { client_id: clientId }),
          ...(workflowId && { workflow_id: workflowId }),
          include_debug: includeDebug,
        },
      }),
      providesTags: ["Executions"],
    }),
    getExecutionDetail: build.query<ExecutionDetailResponse, string>({
      query: (executionId) => ({
        url: `/executions/${executionId}`,
        method: "GET",
      }),
      providesTags: (result) => [{ type: "Executions", id: result?.id }],
    }),
  }),
});

export const { useGetExecutionsQuery, useGetExecutionDetailQuery } =
  executionApi;
