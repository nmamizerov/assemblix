import { useMemo } from "react";
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
import { Button } from "@/shared/ui/button";
import { useUpdateWorkflowMutation } from "../../api/workflow.api";
import type { Workflow } from "../../model/types";

type FormValues = {
  name: string;
};

interface RenameWorkflowModalProps {
  workflow: Workflow;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

export const RenameWorkflowModal = ({
  workflow,
  open,
  onOpenChange,
  onSuccess,
}: RenameWorkflowModalProps) => {
  const { t } = useTranslation();
  const [updateWorkflow, { isLoading }] = useUpdateWorkflowMutation();

  const formSchema = useMemo(
    () =>
      z.object({
        name: z
          .string()
          .min(3, { message: t("workflowActions.nameMinLength") }),
      }),
    [t]
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: workflow.name,
    },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await updateWorkflow({
        ...workflow,
        name: values.name,
        state: undefined,
      }).unwrap();

      toast.success(t("workflowActions.renamed"));
      onOpenChange(false);
      form.reset();

      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      console.error(error);
      toast.error(t("versionsDropdown.error"), {
        description: t("workflowActions.renameError"),
      });
    }
  };

  const handleCancel = () => {
    onOpenChange(false);
    form.reset({ name: workflow.name });
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
          <DialogTitle>{t("workflowActions.renameAgent")}</DialogTitle>
          <DialogDescription>
            {t("workflowActions.renameDescription")}
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
                  <FormLabel>{t("workflowActions.nameLabel")}</FormLabel>
                  <FormControl>
                    <Input
                      placeholder={t("workflowActions.namePlaceholder")}
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
                {t("workflowActions.cancel")}
              </Button>
              <Button type="button" onClick={handleSave} disabled={isLoading} className="gap-2">
                {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
                <Check className="h-4 w-4" />
                {t("workflowActions.save")}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};
