import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Plus,
  Pencil,
  Trash2,
  Loader2,
  X,
  Check,
  Send,
  Bell,
} from "lucide-react";
import { useSelector } from "react-redux";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

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
import { Switch } from "@/shared/ui/switch";
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
  useGetNotificationChannelsQuery,
  useCreateNotificationChannelMutation,
  useUpdateNotificationChannelMutation,
  useDeleteNotificationChannelMutation,
  useTestNotificationChannelMutation,
} from "../api/notification-channel.api";
import {
  NotificationChannelType,
  type NotificationChannel,
} from "../model/types";

import { selectCurrentProjectId } from "@/entities/organization";

type FormValues = {
  type: NotificationChannelType;
  name: string;
  botToken: string;
  chatId: string;
  isEnabled: boolean;
};

type EditState = string | null; // "new" | channelId | null

type NotificationChannelsManagerProps = {
  className?: string;
};

export const NotificationChannelsManager = ({
  className,
}: NotificationChannelsManagerProps) => {
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);

  const [editingId, setEditingId] = useState<EditState>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: channels, isLoading } = useGetNotificationChannelsQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );

  const isEmpty =
    !isLoading && channels && channels.length === 0 && editingId !== "new";

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <div className="flex-1 space-y-3">
        {editingId === "new" && (
          <NotificationChannelEditForm onClose={() => setEditingId(null)} />
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : isEmpty ? (
          <div className="text-center py-8">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Bell className="h-6 w-6 text-primary" />
            </div>
            <p className="text-muted-foreground mb-4">
              {t("notifications.empty")}
            </p>
            <Button
              onClick={() => setEditingId("new")}
              variant="outline"
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              {t("notifications.addFirst")}
            </Button>
          </div>
        ) : (
          channels?.map((channel) =>
            editingId === channel.id ? (
              <NotificationChannelEditForm
                key={channel.id}
                channel={channel}
                onClose={() => setEditingId(null)}
              />
            ) : deletingId === channel.id ? (
              <NotificationChannelDeleteConfirm
                key={channel.id}
                channel={channel}
                onClose={() => setDeletingId(null)}
              />
            ) : (
              <NotificationChannelViewItem
                key={channel.id}
                channel={channel}
                onEdit={() => setEditingId(channel.id)}
                onDelete={() => setDeletingId(channel.id)}
              />
            )
          )
        )}
      </div>

      {!editingId && !deletingId && channels && channels.length > 0 && (
        <div className="border-t pt-4">
          <Button onClick={() => setEditingId("new")} className="gap-2">
            <Plus className="h-4 w-4" />
            {t("notifications.add")}
          </Button>
        </div>
      )}
    </div>
  );
};

const NotificationChannelViewItem = ({
  channel,
  onEdit,
  onDelete,
}: {
  channel: NotificationChannel;
  onEdit: () => void;
  onDelete: () => void;
}) => {
  const { t } = useTranslation();
  const [testChannel, { isLoading: isTesting }] =
    useTestNotificationChannelMutation();

  const handleTest = async () => {
    try {
      const result = await testChannel(channel.id).unwrap();
      if (result.success) {
        toast.success(t("notifications.testSuccess"));
      } else {
        toast.error(t("notifications.testError"), {
          description: result.detail || undefined,
        });
      }
    } catch (error) {
      console.error(error);
      toast.error(t("notifications.testError"));
    }
  };

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Send className="h-5 w-5 text-primary" />
          <div>
            <h3 className="font-semibold text-foreground truncate">
              {channel.name || t("notifications.untitled")}
            </h3>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="rounded-full bg-primary/10 px-2 py-0.5 font-medium text-primary">
                {channel.type}
              </span>
              {!channel.isEnabled && (
                <span className="rounded-full bg-muted px-2 py-0.5 font-medium">
                  {t("notifications.disabled")}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={handleTest}
            disabled={isTesting}
            className="h-8 gap-1.5 px-2"
          >
            {isTesting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            <span className="text-xs">{t("notifications.test")}</span>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onEdit}
            className="h-8 w-8 p-0"
          >
            <Pencil className="h-4 w-4" />
            <span className="sr-only">{t("common.edit")}</span>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={onDelete}
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

const NotificationChannelEditForm = ({
  channel,
  onClose,
}: {
  channel?: NotificationChannel;
  onClose: () => void;
}) => {
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const [createChannel, { isLoading: isCreating }] =
    useCreateNotificationChannelMutation();
  const [updateChannel, { isLoading: isUpdating }] =
    useUpdateNotificationChannelMutation();

  const isEditing = !!channel;
  const isLoading = isCreating || isUpdating;

  const formSchema = useMemo(
    () =>
      z.object({
        type: z.nativeEnum(NotificationChannelType),
        name: z.string(),
        botToken: z.string(),
        chatId: z.string(),
        isEnabled: z.boolean(),
      }),
    []
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      type: channel?.type || NotificationChannelType.TELEGRAM,
      name: channel?.name || "",
      botToken: "",
      chatId: channel?.data?.chat_id || "",
      isEnabled: channel?.isEnabled ?? true,
    },
  });

  const onSubmit = async (values: FormValues) => {
    const botToken = values.botToken.trim();
    const chatId = values.chatId.trim();

    try {
      if (!isEditing) {
        if (!currentProjectId) {
          toast.error(t("agents.selectProject"));
          return;
        }
        if (!botToken || !chatId) {
          if (!botToken)
            form.setError("botToken", {
              type: "manual",
              message: t("notifications.botTokenRequired"),
            });
          if (!chatId)
            form.setError("chatId", {
              type: "manual",
              message: t("notifications.chatIdRequired"),
            });
          return;
        }
        await createChannel({
          projectId: currentProjectId,
          type: values.type,
          name: values.name || null,
          data: { bot_token: botToken, chat_id: chatId },
          isEnabled: values.isEnabled,
        }).unwrap();
        toast.success(t("notifications.createSuccess"));
      } else {
        // Секреты передаём только если пользователь ввёл новый токен —
        // тогда data перезаписывается полностью (нужны оба поля).
        const patch: Parameters<typeof updateChannel>[0] = {
          id: channel.id,
          name: values.name || null,
          isEnabled: values.isEnabled,
        };
        if (botToken) {
          if (!chatId) {
            form.setError("chatId", {
              type: "manual",
              message: t("notifications.chatIdRequired"),
            });
            return;
          }
          patch.data = { bot_token: botToken, chat_id: chatId };
        }
        await updateChannel(patch).unwrap();
        toast.success(t("notifications.updateSuccess"));
      }
      onClose();
      form.reset();
    } catch (error) {
      console.error(error);
      toast.error(t("errors.generic"), {
        description: isEditing
          ? t("notifications.updateError")
          : t("notifications.createError"),
      });
    }
  };

  const handleCancel = () => {
    onClose();
    form.reset();
  };

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
          <FormField
            control={form.control}
            name="type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("notifications.type")}</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                  disabled={isEditing}
                >
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value={NotificationChannelType.TELEGRAM}>
                      Telegram
                    </SelectItem>
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
                <FormLabel>{t("notifications.name")}</FormLabel>
                <FormControl>
                  <Input
                    placeholder={t("notifications.namePlaceholder")}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="botToken"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("notifications.botToken")}</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    placeholder={
                      isEditing
                        ? t("notifications.botTokenEditPlaceholder")
                        : t("notifications.botTokenPlaceholder")
                    }
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="chatId"
            render={({ field }) => (
              <FormItem>
                <FormLabel>{t("notifications.chatId")}</FormLabel>
                <FormControl>
                  <Input
                    placeholder={t("notifications.chatIdPlaceholder")}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="isEnabled"
            render={({ field }) => (
              <FormItem className="flex items-center justify-between rounded-lg border border-border p-3">
                <FormLabel className="cursor-pointer">
                  {t("notifications.enabled")}
                </FormLabel>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
              </FormItem>
            )}
          />

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

const NotificationChannelDeleteConfirm = ({
  channel,
  onClose,
}: {
  channel: NotificationChannel;
  onClose: () => void;
}) => {
  const { t } = useTranslation();
  const [deleteChannel, { isLoading }] = useDeleteNotificationChannelMutation();

  const handleDelete = async () => {
    try {
      await deleteChannel(channel.id).unwrap();
      toast.success(t("notifications.deleteSuccess"));
      onClose();
    } catch (error) {
      console.error(error);
      toast.error(t("errors.generic"), {
        description: t("notifications.deleteError"),
      });
    }
  };

  return (
    <div className="rounded-lg border border-destructive bg-destructive/10 p-4">
      <div className="space-y-3">
        <div>
          <h3 className="font-semibold text-foreground">
            {t("notifications.deleteConfirm")}
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            {t("notifications.deleteWarning", {
              name: channel.name || t("notifications.untitled"),
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
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
        </div>
      </div>
    </div>
  );
};
