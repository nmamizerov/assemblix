import { baseApi } from "@/shared/api/baseApi";
import type {
  Project,
  CreateProjectRequest,
  UpdateProjectRequest,
} from "../model/types";

export const projectApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getProjects: build.query<
      Project[],
      { skip?: number; limit?: number; isActive?: boolean }
    >({
      query: ({ skip = 0, limit = 100, isActive } = {}) => ({
        url: "/projects/",
        method: "GET",
        params: {
          skip,
          limit,
          ...(isActive !== undefined && { is_active: isActive }),
        },
      }),
      providesTags: ["Projects"],
    }),
    getProject: build.query<Project, string>({
      query: (projectId) => ({
        url: `/projects/${projectId}`,
        method: "GET",
      }),
      providesTags: (_result, _error, projectId) => [
        { type: "Projects", id: projectId },
      ],
    }),
    createProject: build.mutation<Project, CreateProjectRequest>({
      query: (body) => ({
        url: "/projects/",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Projects"],
    }),
    updateProject: build.mutation<
      Project,
      { projectId: string; data: UpdateProjectRequest }
    >({
      query: ({ projectId, data }) => ({
        url: `/projects/${projectId}`,
        method: "PATCH",
        body: data,
      }),
      invalidatesTags: (_result, _error, { projectId }) => [
        { type: "Projects", id: projectId },
        "Projects",
      ],
    }),
    deleteProject: build.mutation<void, string>({
      query: (projectId) => ({
        url: `/projects/${projectId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Projects"],
    }),
  }),
});

export const {
  useGetProjectsQuery,
  useGetProjectQuery,
  useCreateProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
} = projectApi;
