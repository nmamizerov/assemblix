import { baseApi } from "@/shared/api/baseApi";
import type {
  NotificationChannel,
  CreateNotificationChannel,
  UpdateNotificationChannel,
  NotificationChannelTestResult,
} from "../model/types";

interface GetNotificationChannelsParams {
  projectId: string;
}

export const notificationChannelApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getNotificationChannels: build.query<
      NotificationChannel[],
      GetNotificationChannelsParams
    >({
      query: ({ projectId }) => ({
        url: "/notification-channels/",
        method: "GET",
        params: { project_id: projectId },
      }),
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ id }) => ({
                type: "NotificationChannels" as const,
                id,
              })),
              { type: "NotificationChannels", id: "LIST" },
            ]
          : [{ type: "NotificationChannels", id: "LIST" }],
    }),
    createNotificationChannel: build.mutation<
      NotificationChannel,
      CreateNotificationChannel & { projectId: string }
    >({
      query: ({ projectId, ...body }) => ({
        url: "/notification-channels/",
        method: "POST",
        params: { project_id: projectId },
        body,
      }),
      invalidatesTags: [{ type: "NotificationChannels", id: "LIST" }],
    }),
    updateNotificationChannel: build.mutation<
      NotificationChannel,
      { id: string } & UpdateNotificationChannel
    >({
      query: ({ id, ...patch }) => ({
        url: `/notification-channels/${id}`,
        method: "PATCH",
        body: patch,
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: "NotificationChannels", id },
        { type: "NotificationChannels", id: "LIST" },
      ],
    }),
    deleteNotificationChannel: build.mutation<void, string>({
      query: (id) => ({
        url: `/notification-channels/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, id) => [
        { type: "NotificationChannels", id },
        { type: "NotificationChannels", id: "LIST" },
      ],
    }),
    testNotificationChannel: build.mutation<NotificationChannelTestResult, string>(
      {
        query: (id) => ({
          url: `/notification-channels/${id}/test`,
          method: "POST",
        }),
      }
    ),
  }),
});

export const {
  useGetNotificationChannelsQuery,
  useCreateNotificationChannelMutation,
  useUpdateNotificationChannelMutation,
  useDeleteNotificationChannelMutation,
  useTestNotificationChannelMutation,
} = notificationChannelApi;
