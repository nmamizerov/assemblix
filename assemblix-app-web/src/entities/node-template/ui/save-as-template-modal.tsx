import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, X, Check } from "lucide-react";
import { toast } from "sonner";

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
import { Input } from "@/shared/ui/input";
import { Textarea } from "@/shared/ui/textarea";
import { Button } from "@/shared/ui/button";
import { useCreateNodeTemplateMutation } from "../api/node-template.api";
import type { NodeTemplateConfig } from "../model/types";

type FormValues = {
  name: string;
  description?: string;
};

interface SaveAsTemplateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  nodeConfig: NodeTemplateConfig;
  projectId: string;
  onSuccess?: () => void;
}

export const SaveAsTemplateModal = ({
  open,
  onOpenChange,
  nodeConfig,
  projectId,
  onSuccess,
}: SaveAsTemplateModalProps) => {
  const { t } = useTranslation();
  const [createNodeTemplate, { isLoading }] = useCreateNodeTemplateMutation();

  const formSchema = z.object({
    name: z
      .string()
      .min(1, { message: t("nodeTemplates.modal.nameRequired") })
      .max(255, { message: t("nodeTemplates.modal.nameMaxLength") }),
    description: z
      .string()
      .max(1000, { message: t("nodeTemplates.modal.descriptionMaxLength") })
      .optional()
      .or(z.literal("")),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await createNodeTemplate({
        projectId,
        name: values.name,
        description: values.description || undefined,
        config: nodeConfig,
      }).unwrap();

      toast.success(t("nodeTemplates.createSuccess"));
      onOpenChange(false);
      form.reset();

      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      console.error(error);
      toast.error(t("nodeTemplates.createError"));
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
          <DialogTitle>{t("nodeTemplates.modal.title")}</DialogTitle>
          <DialogDescription>
            {t("nodeTemplates.modal.description")}
          </DialogDescription>
        </DialogHeader>

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
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("nodeTemplates.modal.name")}</FormLabel>
                  <FormControl>
                    <Input
                      placeholder={t("nodeTemplates.modal.namePlaceholder")}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t("nodeTemplates.modal.templateDescription")}
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder={t(
                        "nodeTemplates.modal.descriptionPlaceholder",
                      )}
                      className="resize-none"
                      rows={3}
                      {...field}
                    />
                  </FormControl>
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
      </DialogContent>
    </Dialog>
  );
};
