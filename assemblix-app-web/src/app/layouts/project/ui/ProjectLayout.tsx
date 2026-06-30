import { useEffect } from "react";
import { useParams, Navigate, Outlet } from "react-router-dom";
import { useAppDispatch } from "@/app/store/store";
import { setCurrentProject } from "@/entities/organization/model/workspace.slice";
import { useGetProjectsQuery } from "@/entities/project";

export const ProjectLayout = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const dispatch = useAppDispatch();
  const { data: projects, isLoading } = useGetProjectsQuery({});

  useEffect(() => {
    if (projectId && projects?.some((p) => p.id === projectId)) {
      dispatch(setCurrentProject(projectId));
    }
  }, [projectId, projects, dispatch]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!projects?.length) {
    return null;
  }

  if (!projectId || !projects.some((p) => p.id === projectId)) {
    return <Navigate to={`/projects/${projects[0].id}/workflows`} replace />;
  }

  return <Outlet />;
};
