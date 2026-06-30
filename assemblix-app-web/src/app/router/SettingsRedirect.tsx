import { Navigate, useParams } from "react-router-dom";

type SettingsRedirectProps = {
  to: "general" | "api-keys" | "credentials";
};

export const SettingsRedirect = ({ to }: SettingsRedirectProps) => {
  const { projectId } = useParams();
  return <Navigate to={`/projects/${projectId}/settings/${to}`} replace />;
};
