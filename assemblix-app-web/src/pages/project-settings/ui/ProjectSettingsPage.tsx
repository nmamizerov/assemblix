import { useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { Loader2, Plus, Trash2, Settings as SettingsIcon } from "lucide-react";
import {
  useGetProjectQuery,
  useUpdateProjectMutation,
} from "@/entities/project";
import { selectCurrentProjectId } from "@/entities/organization";
import { useGetBillingUsageQuery, FeatureLockedCard } from "@/entities/billing";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { toast } from "sonner";
import { VariableForm, type VariableFormData } from "@/features/variable-form";

export const ProjectSettingsPage = () => {
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const [addVariableOpen, setAddVariableOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [variableToDelete, setVariableToDelete] = useState<number | null>(null);

  const { data: project, isLoading } = useGetProjectQuery(currentProjectId!, {
    skip: !currentProjectId,
  });

  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });

  const [updateProject, { isLoading: isUpdating }] = useUpdateProjectMutation();

  const stateSchema = project?.stateSchema || [];
  const hasProjectVariables = billingUsage?.features.projectVariables ?? true;

  const handleAddVariable = async (data: VariableFormData) => {
    try {
      const newVariable = {
        name: data.name,
        type: data.type,
        defaultValue: data.defaultValue ?? null,
      };
      await updateProject({
        projectId: currentProjectId!,
        data: {
          stateSchema: [...stateSchema, newVariable],
        },
      }).unwrap();
      toast.success(t("projectSettings.variableAdded"));
      setAddVariableOpen(false);
    } catch (error) {
      console.error(error);
      // Обработка ошибки 403 (фича недоступна на текущем плане)
      if (
        error &&
        typeof error === "object" &&
        "status" in error &&
        error.status === 403
      ) {
        const errorData = error as {
          status: number;
          data?: { detail?: string };
        };
        toast.error(
          errorData.data?.detail || t("billing.errors.featureNotAvailable")
        );
      } else {
        toast.error(t("projectSettings.addError"));
      }
    }
  };

  const handleDeleteVariable = async () => {
    if (variableToDelete === null) return;

    const updatedSchema = stateSchema.filter(
      (_, index) => index !== variableToDelete
    );

    try {
      await updateProject({
        projectId: currentProjectId!,
        data: {
          stateSchema: updatedSchema,
        },
      }).unwrap();
      toast.success(t("projectSettings.variableDeleted"));
      setDeleteDialogOpen(false);
      setVariableToDelete(null);
    } catch (error) {
      console.error(error);
      // Обработка ошибки 403
      if (
        error &&
        typeof error === "object" &&
        "status" in error &&
        error.status === 403
      ) {
        const errorData = error as {
          status: number;
          data?: { detail?: string };
        };
        toast.error(
          errorData.data?.detail || t("billing.errors.featureNotAvailable")
        );
      } else {
        toast.error(t("projectSettings.deleteError"));
      }
    }
  };

  const openDeleteDialog = (index: number) => {
    setVariableToDelete(index);
    setDeleteDialogOpen(true);
  };

  if (isLoading || !project) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {t("projectSettings.title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("projectSettings.subtitle")}
        </p>
      </div>

      {/* Project Info */}
      <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            <SettingsIcon className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">
              {t("projectSettings.projectInfo")}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t("projectSettings.projectInfoDescription")}
            </p>
          </div>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-muted-foreground">
              {t("common.name")}
            </dt>
            <dd className="mt-1 text-sm font-medium">{project.name}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-muted-foreground">Slug</dt>
            <dd className="mt-1 text-sm font-mono">{project.slug}</dd>
          </div>
          {project.description && (
            <div className="sm:col-span-2">
              <dt className="text-sm font-medium text-muted-foreground">
                {t("common.description")}
              </dt>
              <dd className="mt-1 text-sm">{project.description}</dd>
            </div>
          )}
        </dl>
      </div>

      {/* State Schema */}
      <div className="rounded-lg border border-border bg-card shadow-sm">
        <div className="border-b border-border p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold">
                {t("projectSettings.stateSchema")}
              </h2>
              <p className="text-sm text-muted-foreground">
                {t("projectSettings.stateSchemaDescription")}
              </p>
            </div>
            {hasProjectVariables && (
              <Button onClick={() => setAddVariableOpen(true)} size="lg">
                <Plus className="mr-2 h-5 w-5" />
                {t("projectSettings.addVariable")}
              </Button>
            )}
          </div>
        </div>

        {!hasProjectVariables ? (
          <div className="p-6">
            <FeatureLockedCard
              featureName={t("billing.features.projectVariables.name")}
              featureDescription={t(
                "billing.features.projectVariables.description"
              )}
              requiredPlan="starter"
            />
          </div>
        ) : stateSchema.length === 0 ? (
          <div className="flex min-h-[200px] flex-col items-center justify-center p-6 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <SettingsIcon className="h-8 w-8 text-primary" />
            </div>
            <h3 className="mt-4 text-lg font-semibold">
              {t("projectSettings.noVariables")}
            </h3>
            <p className="mt-2 max-w-sm text-sm text-muted-foreground">
              {t("projectSettings.noVariablesDescription")}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-border bg-muted/50">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                    {t("projectSettings.variableName")}
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                    {t("projectSettings.variableType")}
                  </th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                    {t("projectSettings.defaultValue")}
                  </th>
                  <th className="px-6 py-4 text-right text-sm font-semibold text-foreground">
                    {t("common.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {stateSchema.map((variable, index) => (
                  <tr
                    key={index}
                    className="transition-colors hover:bg-muted/50"
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono text-sm font-medium">
                        {variable.name}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                        {variable.type}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-muted-foreground">
                        {typeof variable.defaultValue === "object"
                          ? JSON.stringify(variable.defaultValue)
                          : String(variable.defaultValue)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openDeleteDialog(index)}
                        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Variable Dialog */}
      <Dialog open={addVariableOpen} onOpenChange={setAddVariableOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("projectSettings.addVariable")}</DialogTitle>
            <DialogDescription>
              {t("projectSettings.addVariableDescription")}
            </DialogDescription>
          </DialogHeader>
          <VariableForm
            existingNames={stateSchema.map((v) => v.name)}
            onSubmit={handleAddVariable}
            onCancel={() => setAddVariableOpen(false)}
            isLoading={isUpdating}
          />
        </DialogContent>
      </Dialog>

      {/* Delete Variable Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("projectSettings.deleteVariable")}</DialogTitle>
            <DialogDescription>
              {t("projectSettings.deleteVariableWarning")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isUpdating}
            >
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteVariable}
              disabled={isUpdating}
            >
              {isUpdating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("common.deleting")}
                </>
              ) : (
                t("common.delete")
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
