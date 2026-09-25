import { Navigate } from "react-router-dom";
import { useSelector } from "react-redux";
import { useGetProjectsQuery } from "@/entities/project";
import { selectCurrentProjectId } from "@/entities/organization/model/workspace.slice";

export const RootRedirect = () => {
  const { data: projects, isLoading } = useGetProjectsQuery({});
  const currentProjectId = useSelector(selectCurrentProjectId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (projects?.length) {
    const project =
      projects.find((p) => p.id === currentProjectId) ?? projects[0];
    return <Navigate to={`/projects/${project.id}/workflows`} replace />;
  }

  return <Navigate to="/auth/login" replace />;
};
