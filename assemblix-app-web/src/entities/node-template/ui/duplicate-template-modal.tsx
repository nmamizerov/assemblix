import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, X, Check } from "lucide-react";
import { toast } from "sonner";
import { useMemo } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/shared/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Button } from "@/shared/ui/button";
import { useCreateNodeTemplateMutation } from "../api/node-template.api";
import { useGetProjectsQuery } from "@/entities/project";
import type { NodeTemplate } from "../model/types";

type FormValues = {
  projectId: string;
};

interface DuplicateTemplateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template: NodeTemplate;
  currentProjectId: string;
  onSuccess?: () => void;
}

export const DuplicateTemplateModal = ({
  open,
  onOpenChange,
  template,
  currentProjectId,
  onSuccess,
}: DuplicateTemplateModalProps) => {
  const { t } = useTranslation();
  const [createNodeTemplate, { isLoading }] = useCreateNodeTemplateMutation();
  const { data: projects, isLoading: isLoadingProjects } = useGetProjectsQuery(
    {},
  );

  const formSchema = z.object({
    projectId: z.string().min(1, { message: t("agents.selectProject") }),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      projectId: "",
    },
  });

  // Filter out current project
  const availableProjects = useMemo(() => {
    if (!projects) return [];
    return projects.filter((p) => p.id !== currentProjectId);
  }, [projects, currentProjectId]);

  const onSubmit = async (values: FormValues) => {
    try {
      await createNodeTemplate({
        projectId: values.projectId,
        name: template.name,
        description: template.description || undefined,
        config: template.config,
      }).unwrap();

      toast.success(t("nodeTemplates.duplicateSuccess"));
      onOpenChange(false);
      form.reset();

      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      console.error(error);
      toast.error(t("nodeTemplates.duplicateError"));
    }
  };

  const handleCancel = () => {
    onOpenChange(false);
    form.reset();
  };

  const handleSave = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    await form.handleSubmit(onSubmit)();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("nodeTemplates.duplicateModal.title")}</DialogTitle>
          <DialogDescription>
            {t("nodeTemplates.duplicateModal.description")}
          </DialogDescription>
        </DialogHeader>

        {isLoadingProjects ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : availableProjects.length === 0 ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-muted/50 p-4">
              <p className="text-sm text-muted-foreground text-center">
                {t("nodeTemplates.duplicateModal.noOtherProjects")}
              </p>
            </div>
            <div className="flex justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                className="gap-2"
              >
                <X className="h-4 w-4" />
                {t("common.close")}
              </Button>
            </div>
          </div>
        ) : (
          <Form {...form}>
            <form
              onSubmit={(e) => {
                e.stopPropagation();
                form.handleSubmit(onSubmit)(e);
              }}
              className="space-y-4"
            >
              <FormField
                control={form.control}
                name="projectId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {t("nodeTemplates.duplicateModal.selectProject")}
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue
                            placeholder={t(
                              "nodeTemplates.duplicateModal.selectProject",
                            )}
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className="z-[9999]">
                        {availableProjects.map((project) => (
                          <SelectItem key={project.id} value={project.id}>
                            {project.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="flex gap-2 justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCancel}
                  disabled={isLoading}
                  className="gap-2"
                >
                  <X className="h-4 w-4" />
                  {t("common.cancel")}
                </Button>
                <Button
                  type="button"
                  onClick={handleSave}
                  disabled={isLoading}
                  className="gap-2"
                >
                  {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                  <Check className="h-4 w-4" />
                  {t("common.save")}
                </Button>
              </div>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  );
};
