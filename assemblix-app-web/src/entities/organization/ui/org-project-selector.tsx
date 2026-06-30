import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  FolderKanban,
  ChevronDown,
  Check,
  Plus,
} from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  useGetOrganizationsQuery,
  useSetCurrentOrganizationMutation,
  useCreateOrganizationMutation,
  setCurrentOrganization,
  selectCurrentOrganizationId,
  selectCurrentProjectId,
} from "@/entities/organization";
import {
  useGetProjectsQuery,
  useCreateProjectMutation,
} from "@/entities/project";
import { useMeQuery } from "@/entities/session";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Divider } from "@/shared/ui/divider";
import { cn } from "@/shared/lib/utils";
import { toast } from "sonner";

export const OrgProjectSelector = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { data: user } = useMeQuery();
  const currentOrgId = useSelector(selectCurrentOrganizationId);
  const currentProjectId = useSelector(selectCurrentProjectId);

  const [isOrgPopoverOpen, setIsOrgPopoverOpen] = useState(false);
  const [isProjectPopoverOpen, setIsProjectPopoverOpen] = useState(false);
  const [isOrgModalOpen, setIsOrgModalOpen] = useState(false);
  const [isProjectModalOpen, setIsProjectModalOpen] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [projectName, setProjectName] = useState("");

  const { data: organizations = [], isLoading: orgsLoading } =
    useGetOrganizationsQuery({});
  const { data: projects = [], isLoading: projectsLoading } =
    useGetProjectsQuery({}, { skip: !currentOrgId });

  const [setCurrentOrg] = useSetCurrentOrganizationMutation();
  const [createOrganization, { isLoading: isCreatingOrg }] =
    useCreateOrganizationMutation();
  const [createProject, { isLoading: isCreatingProject }] =
    useCreateProjectMutation();

  // Initialize current organization from user data if not set
  useEffect(() => {
    if (!currentOrgId && user?.currentOrganizationId) {
      dispatch(setCurrentOrganization(user.currentOrganizationId));
    } else if (!currentOrgId && organizations.length > 0) {
      // If user doesn't have currentOrganizationId, use first org
      const firstOrg = organizations[0];
      dispatch(setCurrentOrganization(firstOrg.id));
      setCurrentOrg({ organizationId: firstOrg.id });
    }
  }, [currentOrgId, user, organizations, dispatch, setCurrentOrg]);


  const currentOrganization = useMemo(
    () => organizations.find((org) => org.id === currentOrgId),
    [organizations, currentOrgId]
  );

  const currentProject = useMemo(
    () => projects.find((proj) => proj.id === currentProjectId),
    [projects, currentProjectId]
  );

  const handleOrganizationChange = async (orgId: string) => {
    try {
      await setCurrentOrg({ organizationId: orgId }).unwrap();
      dispatch(setCurrentOrganization(orgId));
      setIsOrgPopoverOpen(false);
      navigate("/");
    } catch (error) {
      console.error("Failed to change organization:", error);
    }
  };

  const handleProjectChange = (projectId: string) => {
    navigate(`/projects/${projectId}/workflows`);
    setIsProjectPopoverOpen(false);
  };

  const handleCreateOrganization = async () => {
    if (!orgName.trim()) {
      toast.error(t("organization.enterName"));
      return;
    }

    try {
      const newOrg = await createOrganization({
        name: orgName.trim(),
      }).unwrap();

      toast.success(t("organization.organizationCreated"));
      setIsOrgModalOpen(false);
      setOrgName("");

      // Переключаемся на новую организацию
      await setCurrentOrg({ organizationId: newOrg.id }).unwrap();
      dispatch(setCurrentOrganization(newOrg.id));
    } catch (error) {
      console.error("Failed to create organization:", error);
      toast.error(t("organization.organizationCreateError"));
    }
  };

  const handleCreateProject = async () => {
    if (!projectName.trim()) {
      toast.error(t("organization.enterProjectNameError"));
      return;
    }

    if (!currentOrgId) {
      toast.error(t("organization.selectOrganizationFirst"));
      return;
    }

    try {
      const newProject = await createProject({
        name: projectName.trim(),
      }).unwrap();

      toast.success(t("organization.projectCreated"));
      setIsProjectModalOpen(false);
      setProjectName("");

      // Переключаемся на новый проект
      navigate(`/projects/${newProject.id}/workflows`);
    } catch (error) {
      console.error("Failed to create project:", error);
      toast.error(t("organization.projectCreateError"));
    }
  };

  if (orgsLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Building2 className="h-4 w-4" />
        <span>{t("common.loading")}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5" data-tour="org-selector">
      {/* Organization Selector */}
      <Popover open={isOrgPopoverOpen} onOpenChange={setIsOrgPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-sm font-medium"
          >
            <Building2 className="h-4 w-4 text-muted-foreground" />
            <span className="max-w-[150px] truncate">
              {currentOrganization?.name ||
                t("organization.selectOrganization")}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64 p-2">
          <div className="space-y-0.5">
            {organizations.map((org) => (
              <Button
                key={org.id}
                variant="ghost"
                className={cn(
                  "w-full justify-start gap-3 px-3 font-normal",
                  currentOrgId === org.id && "bg-accent"
                )}
                onClick={() => handleOrganizationChange(org.id)}
              >
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1 truncate text-left">{org.name}</span>
                {currentOrgId === org.id && (
                  <Check className="h-4 w-4 text-primary" />
                )}
              </Button>
            ))}

            <Divider className="my-1" />

            <Button
              variant="ghost"
              className="w-full justify-start gap-3 px-3 font-normal text-primary"
              onClick={() => {
                setIsOrgPopoverOpen(false);
                setIsOrgModalOpen(true);
              }}
            >
              <Plus className="h-4 w-4" />
              <span>{t("organization.addOrganization")}</span>
            </Button>
          </div>
        </PopoverContent>
      </Popover>

      {/* Divider */}
      <span className="text-muted-foreground">/</span>

      {/* Project Selector */}
      <Popover
        open={isProjectPopoverOpen}
        onOpenChange={setIsProjectPopoverOpen}
      >
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-sm font-medium"
            disabled={projectsLoading || projects.length === 0}
          >
            <FolderKanban className="h-4 w-4 text-muted-foreground" />
            <span className="max-w-[150px] truncate">
              {currentProject?.name || t("organization.selectProject")}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64 p-2">
          <div className="space-y-0.5">
            {projects.map((project) => (
              <Button
                key={project.id}
                variant="ghost"
                className={cn(
                  "w-full justify-start gap-3 px-3 font-normal",
                  currentProjectId === project.id && "bg-accent"
                )}
                onClick={() => handleProjectChange(project.id)}
              >
                <FolderKanban className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1 truncate text-left">
                  {project.name}
                </span>
                {currentProjectId === project.id && (
                  <Check className="h-4 w-4 text-primary" />
                )}
              </Button>
            ))}

            <Divider className="my-1" />

            <Button
              variant="ghost"
              className="w-full justify-start gap-3 px-3 font-normal text-primary"
              onClick={() => {
                setIsProjectPopoverOpen(false);
                setIsProjectModalOpen(true);
              }}
            >
              <Plus className="h-4 w-4" />
              <span>{t("organization.addProject")}</span>
            </Button>
          </div>
        </PopoverContent>
      </Popover>

      {/* Модальное окно создания организации */}
      <Dialog open={isOrgModalOpen} onOpenChange={setIsOrgModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("organization.createOrganization")}</DialogTitle>
            <DialogDescription>
              {t("organization.enterOrganizationName")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">
                {t("organization.organizationName")}
              </Label>
              <Input
                id="org-name"
                placeholder={t("organization.organizationNamePlaceholder")}
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isCreatingOrg) {
                    handleCreateOrganization();
                  }
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsOrgModalOpen(false);
                setOrgName("");
              }}
              disabled={isCreatingOrg}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={handleCreateOrganization}
              disabled={isCreatingOrg || !orgName.trim()}
            >
              {isCreatingOrg ? t("organization.creating") : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Модальное окно создания проекта */}
      <Dialog open={isProjectModalOpen} onOpenChange={setIsProjectModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t("organization.createProject")}</DialogTitle>
            <DialogDescription>
              {t("organization.enterProjectName")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="project-name">
                {t("organization.projectName")}
              </Label>
              <Input
                id="project-name"
                placeholder={t("organization.projectNamePlaceholder")}
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isCreatingProject) {
                    handleCreateProject();
                  }
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsProjectModalOpen(false);
                setProjectName("");
              }}
              disabled={isCreatingProject}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={handleCreateProject}
              disabled={isCreatingProject || !projectName.trim()}
            >
              {isCreatingProject
                ? t("organization.creating")
                : t("common.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
