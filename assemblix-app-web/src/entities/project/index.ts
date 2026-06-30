export {
  projectApi,
  useGetProjectsQuery,
  useGetProjectQuery,
  useCreateProjectMutation,
  useUpdateProjectMutation,
  useDeleteProjectMutation,
} from "./api/project.api";

export type {
  Project,
  CreateProjectRequest,
  UpdateProjectRequest,
} from "./model/types";
