import { baseApi } from "@/shared/api/baseApi";
import type {
  NodeTemplate,
  CreateNodeTemplateRequest,
  UpdateNodeTemplateRequest,
} from "../model/types";

interface GetNodeTemplatesParams {
  projectId: string;
  skip?: number;
  limit?: number;
}

export const nodeTemplateApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getNodeTemplates: build.query<NodeTemplate[], GetNodeTemplatesParams>({
      query: ({ projectId, skip = 0, limit = 100 }) => ({
        url: "/node-templates/",
        method: "GET",
        params: {
          project_id: projectId,
          skip,
          limit,
        },
      }),
      providesTags: ["NodeTemplates"],
    }),
    getNodeTemplate: build.query<NodeTemplate, string>({
      query: (templateId) => ({
        url: `/node-templates/${templateId}`,
        method: "GET",
      }),
      providesTags: (result) => [
        { type: "NodeTemplates", id: result?.id },
      ],
    }),
    createNodeTemplate: build.mutation<
      NodeTemplate,
      CreateNodeTemplateRequest
    >({
      query: (body) => ({
        url: "/node-templates/",
        method: "POST",
        body,
      }),
      invalidatesTags: ["NodeTemplates"],
    }),
    updateNodeTemplate: build.mutation<
      NodeTemplate,
      { templateId: string; data: UpdateNodeTemplateRequest }
    >({
      query: ({ templateId, data }) => ({
        url: `/node-templates/${templateId}`,
        method: "PATCH",
        body: data,
      }),
      invalidatesTags: (_result, _error, { templateId }) => [
        { type: "NodeTemplates", id: templateId },
        "NodeTemplates",
      ],
    }),
    deleteNodeTemplate: build.mutation<void, string>({
      query: (templateId) => ({
        url: `/node-templates/${templateId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["NodeTemplates"],
    }),
  }),
});

export const {
  useGetNodeTemplatesQuery,
  useGetNodeTemplateQuery,
  useCreateNodeTemplateMutation,
  useUpdateNodeTemplateMutation,
  useDeleteNodeTemplateMutation,
} = nodeTemplateApi;
