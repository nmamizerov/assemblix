import { Navigate } from "react-router-dom";
import { useGetProjectsQuery } from "@/entities/project";

export const RootRedirect = () => {
  const { data: projects, isLoading } = useGetProjectsQuery({});

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (projects?.length) {
    return <Navigate to={`/projects/${projects[0].id}/workflows`} replace />;
  }

  return <Navigate to="/auth/login" replace />;
};
