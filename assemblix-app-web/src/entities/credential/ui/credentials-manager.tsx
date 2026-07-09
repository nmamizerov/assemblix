import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Pencil, Trash2, Loader2, X, Check } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useMemo } from "react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Divider } from "@/shared/ui/divider";
import { cn } from "@/shared/lib/utils";

import {
  useGetCredentialsQuery,
  useCreateCredentialMutation,
  useUpdateCredentialMutation,
  useDeleteCredentialMutation,
} from "../api/credential.api";
import {
  selectEditingId,
  selectDeletingId,
  selectOnCreatedCallback,
  startEditing,
  startCreating,
  cancelEditing,
  startDeleting,
  cancelDeleting,
} from "../model/credential.slice";
import { CredentialType, type Credential } from "../model/types";
import { CREDENTIAL_TYPE_CONFIG, getAllCredentialTypes } from "../model/config";

import { selectCurrentProjectId } from "@/entities/organization";

type FormValues = {
  type: CredentialType;
  name: string;
  value?: string;
  // Yandex SpeechKit needs two secrets; they are joined into `value` on submit.
  apiKey?: string;
  folderId?: string;
};

type CredentialsManagerProps = {
  className?: string;
};

export const CredentialsManager = ({ className }: CredentialsManagerProps) => {
  const dispatch = useDispatch();
  const editingId = useSelector(selectEditingId);
  const deletingId = useSelector(selectDeletingId);
  const onCreatedCallback = useSelector(selectOnCreatedCallback);
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { t } = useTranslation();

  const { data: credentials, isLoading } = useGetCredentialsQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );

  const handleCreate = () => {
    dispatch(startCreating());
  };

  const isEmpty =
    !isLoading && credentials && credentials.length === 0 && editingId !== "new";

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex-1 space-y-3">
        {editingId === "new" && (
          <CredentialEditForm onCreatedCallback={onCreatedCallback} />
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : isEmpty ? (
          <div className="text-center py-8">
            <p className="text-muted-foreground mb-4">
              {t("credentials.noCredentials")}
            </p>
            <Button
              onClick={handleCreate}
              variant="outline"
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              {t("credentials.addFirstCredential")}
            </Button>
          </div>
        ) : (
          credentials?.map((credential) =>
            editingId === credential.id ? (
              <CredentialEditForm
                key={credential.id}
                credential={credential}
                onCreatedCallback={onCreatedCallback}
              />
            ) : deletingId === credential.id ? (
              <CredentialDeleteConfirm
                key={credential.id}
                credential={credential}
              />
            ) : (
              <CredentialViewItem key={credential.id} credential={credential} />
            )
          )
        )}
      </div>

      {!editingId && !deletingId && credentials && credentials.length > 0 && (
        <div className="border-t pt-4">
          <Button onClick={handleCreate} className="gap-2">
            <Plus className="h-4 w-4" />
            {t("credentials.addCredential")}
          </Button>
        </div>
      )}
    </div>
  );
};

const CredentialViewItem = ({ credential }: { credential: Credential }) => {
  const dispatch = useDispatch();
  const config = CREDENTIAL_TYPE_CONFIG[credential.type];
  const { t } = useTranslation();

  return (
    <div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 justify-center">
          <img src={config.icon} alt={config.label} className="w-5 h-5" />
          <h3 className="font-semibold text-foreground truncate">
            {credential.name || t("credentials.untitled")}
          </h3>
        </div>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => dispatch(startEditing(credential.id))}
            className="h-8 w-8 p-0"
          >
            <Pencil className="h-4 w-4" />
            <span className="sr-only">{t("common.edit")}</span>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => dispatch(startDeleting(credential.id))}
            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
            <span className="sr-only">{t("common.delete")}</span>
          </Button>
        </div>
      </div>
    </div>
  );
};

const CredentialEditForm = ({
  credential,
  onCreatedCallback,
}: {
  credential?: Credential;
  onCreatedCallback?: (credentialId: string) => void;
}) => {
  const dispatch = useDispatch();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { t } = useTranslation();
  const [createCredential, { isLoading: isCreating }] =
    useCreateCredentialMutation();
  const [updateCredential, { isLoading: isUpdating }] =
    useUpdateCredentialMutation();

  const isEditing = !!credential;
  const isLoading = isCreating || isUpdating;

  const formSchema = useMemo(
    () =>
      z.object({
        type: z.nativeEnum(CredentialType, {
          message: t("credentials.selectCredentialType"),
        }),
        name: z.string().min(3, { message: t("credentials.nameMinLength") }),
        value: z.string().optional(),
        apiKey: z.string().optional(),
        folderId: z.string().optional(),
      }),
    [t]
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      type: credential?.type || CredentialType.OPENAI_TOKEN,
      name: credential?.name || "",
      value: "",
      apiKey: "",
      folderId: "",
    },
  });

  const isYandex =
    form.watch("type") === CredentialType.YANDEX_SPEECHKIT_TOKEN;

  const onSubmit = async (values: FormValues) => {
    try {
      // Yandex stores two secrets in one credential as "<folderId>:<apiKey>".
      let value = values.value;
      if (values.type === CredentialType.YANDEX_SPEECHKIT_TOKEN) {
        const apiKey = (values.apiKey ?? "").trim();
        const folderId = (values.folderId ?? "").trim();
        if (isEditing && !apiKey && !folderId) {
          value = undefined; // leave the stored value unchanged
        } else if (!apiKey || !folderId) {
          if (!apiKey)
            form.setError("apiKey", {
              type: "manual",
              message: t("credentials.valueRequired"),
            });
          if (!folderId)
            form.setError("folderId", {
              type: "manual",
              message: t("credentials.valueRequired"),
            });
          return;
        } else {
          value = `${folderId}:${apiKey}`;
        }
      }

      if (!isEditing && (!value || value.trim() === "")) {
        form.setError("value", {
          type: "manual",
          message: t("credentials.valueRequired"),
        });
        return;
      }

      if (isEditing) {
        await updateCredential({
          id: credential.id,
          name: values.name,
          value: value || undefined,
        }).unwrap();
        toast.success(t("credentials.updateSuccess"));
      } else {
        if (!currentProjectId) {
          toast.error(t("agents.selectProject"));
          return;
        }
        const newCredential = await createCredential({
          type: values.type,
          name: values.name,
          value: value!,
          projectId: currentProjectId,
        }).unwrap();
        toast.success(t("credentials.createSuccess"));
        if (onCreatedCallback) {
          onCreatedCallback(newCredential.id);
        }
      }
      dispatch(cancelEditing());
      form.reset();
    } catch (error) {
      console.error(error);
      toast.error(t("errors.generic"), {
        description: isEditing
          ? t("credentials.updateError")
          : t("credentials.createError"),
      });
    }
  };

  const handleCancel = () => {
    dispatch(cancelEditing());
    form.reset();
  };

  return (
    <div className="bg-card">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
          <FormField
            control={form.control}
            name="type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("credentials.type")}</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                  disabled={isEditing}
                >
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder={t("credentials.selectType")} />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {getAllCredentialTypes().map((credentialConfig) => (
                      <SelectItem
                        key={credentialConfig.type}
                        value={credentialConfig.type}
                      >
                        <div className="flex items-center gap-2">
                          <img
                            src={credentialConfig.icon}
                            alt={credentialConfig.label}
                            className="w-5 h-5"
                          />
                          {credentialConfig.label}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("credentials.name")}</FormLabel>
                <FormControl>
                  <Input
                    placeholder={t("credentials.namePlaceholder")}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {isYandex ? (
            <>
              <FormField
                control={form.control}
                name="folderId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("credentials.yandexFolderId")}</FormLabel>
                    <FormControl>
                      <Input
                        placeholder={t("credentials.yandexFolderIdPlaceholder")}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="apiKey"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t("credentials.yandexApiKey")}</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder={
                          isEditing
                            ? t("credentials.newValuePlaceholder")
                            : t("credentials.yandexApiKeyPlaceholder")
                        }
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </>
          ) : (
            <FormField
              control={form.control}
              name="value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {isEditing
                      ? t("credentials.newValue")
                      : t("credentials.value")}
                  </FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder={
                        isEditing
                          ? t("credentials.newValuePlaceholder")
                          : t("credentials.valuePlaceholder")
                      }
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

          <div className="flex gap-2 pt-2">
            <Button type="submit" disabled={isLoading} className="gap-2">
              {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              <Check className="h-4 w-4" />
              {isEditing ? t("common.save") : t("common.create")}
            </Button>
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
          </div>
        </form>
      </Form>
      {!isEditing && <Divider className="mt-4" />}
    </div>
  );
};

const CredentialDeleteConfirm = ({
  credential,
}: {
  credential: Credential;
}) => {
  const dispatch = useDispatch();
  const { t } = useTranslation();
  const [deleteCredential, { isLoading }] = useDeleteCredentialMutation();

  const handleDelete = async () => {
    try {
      await deleteCredential(credential.id).unwrap();
      toast.success(t("credentials.deleteSuccess"));
      dispatch(cancelDeleting());
    } catch (error) {
      console.error(error);
      toast.error(t("errors.generic"), {
        description: t("credentials.deleteError"),
      });
    }
  };

  const handleCancel = () => {
    dispatch(cancelDeleting());
  };

  return (
    <div className="rounded-lg border border-destructive bg-destructive/10 p-4">
      <div className="space-y-3">
        <div>
          <h3 className="font-semibold text-foreground">
            {t("credentials.deleteConfirm")}
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            {t("credentials.deleteWarning", {
              name: credential.name || t("credentials.untitled"),
            })}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={isLoading}
            className="gap-2"
          >
            {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
            {t("common.delete")}
          </Button>
          <Button variant="outline" onClick={handleCancel} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
        </div>
      </div>
    </div>
  );
};
