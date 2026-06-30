export enum NotificationChannelType {
  TELEGRAM = "TELEGRAM",
}

/**
 * Настройки канала. Ключи внутри `data` хранятся в snake_case как их ожидает
 * бэкенд (например, для Telegram: bot_token, chat_id). Секреты в ответах
 * приходят замаскированными ("***").
 */
export type NotificationChannelData = Record<string, string>;

export type NotificationChannel = {
  id: string;
  projectId: string;
  type: NotificationChannelType;
  name: string | null;
  data: NotificationChannelData;
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
};

export type CreateNotificationChannel = {
  type: NotificationChannelType;
  name?: string | null;
  data: NotificationChannelData;
  isEnabled?: boolean;
};

export type UpdateNotificationChannel = {
  name?: string | null;
  data?: NotificationChannelData;
  isEnabled?: boolean;
};

export type NotificationChannelTestResult = {
  success: boolean;
  detail: string | null;
};
