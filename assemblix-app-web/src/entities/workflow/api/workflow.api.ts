import { baseApi } from "@/shared/api/baseApi";
import type { Workflow } from "../model/types";

interface GetWorkflowsParams {
  projectId: string;
}

export const workflowApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getWorkflows: build.query<Workflow[], GetWorkflowsParams>({
      query: ({ projectId }) => ({
        url: "/workflows/",
        method: "GET",
        params: { project_id: projectId },
      }),
      providesTags: ["Workflows"],
    }),
    getWorkflow: build.query<Workflow, string>({
      query: (id) => ({
        url: `/workflows/${id}`,
        method: "GET",
      }),
      providesTags: (result) => [{ type: "Workflows", id: result?.id }],
    }),
    createWorkflow: build.mutation<Workflow, { projectId: string }>({
      query: ({ projectId }) => ({
        url: "/workflows/",
        method: "POST",
        body: { project_id: projectId },
      }),
      invalidatesTags: ["Workflows"],
    }),
    updateWorkflow: build.mutation<Workflow, Workflow>({
      query: (workflow) => ({
        url: `/workflows/${workflow.id}`,
        method: "PATCH",
        body: workflow,
      }),
    }),
    publishWorkflow: build.mutation<Workflow, string>({
      query: (workflowId) => ({
        url: `/workflows/${workflowId}/publish`,
        method: "POST",
      }),
      invalidatesTags: ["Workflows"],
    }),
    copyWorkflow: build.mutation<Workflow, string>({
      query: (workflowId) => ({
        url: `/workflows/${workflowId}/copy`,
        method: "POST",
      }),
      invalidatesTags: ["Workflows"],
    }),
    deleteWorkflow: build.mutation<void, string>({
      query: (workflowId) => ({
        url: `/workflows/${workflowId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Workflows"],
    }),
    moveWorkflow: build.mutation<
      Workflow,
      { workflowId: string; targetProjectId: string }
    >({
      query: ({ workflowId, targetProjectId }) => ({
        url: `/workflows/${workflowId}/move`,
        method: "POST",
        body: { target_project_id: targetProjectId },
      }),
      invalidatesTags: ["Workflows"],
    }),
  }),
});

export const {
  useGetWorkflowsQuery,
  useCreateWorkflowMutation,
  useGetWorkflowQuery,
  useUpdateWorkflowMutation,
  usePublishWorkflowMutation,
  useCopyWorkflowMutation,
  useDeleteWorkflowMutation,
  useMoveWorkflowMutation,
} = workflowApi;
