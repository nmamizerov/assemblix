import { baseApi } from "@/shared/api/baseApi";
import type {
  Organization,
  CreateOrganizationRequest,
  UpdateOrganizationRequest,
  SetCurrentOrganizationRequest,
  SetCurrentOrganizationResponse,
} from "../model/types";

export const organizationApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getOrganizations: build.query<
      Organization[],
      { skip?: number; limit?: number }
    >({
      query: ({ skip = 0, limit = 100 } = {}) => ({
        url: "/organizations/",
        method: "GET",
        params: { skip, limit },
      }),
      providesTags: ["Organizations"],
    }),
    getOrganization: build.query<Organization, string>({
      query: (organizationId) => ({
        url: `/organizations/${organizationId}`,
        method: "GET",
      }),
      providesTags: (_result, _error, organizationId) => [
        { type: "Organizations", id: organizationId },
      ],
    }),
    createOrganization: build.mutation<Organization, CreateOrganizationRequest>(
      {
        query: (body) => ({
          url: "/organizations/",
          method: "POST",
          body,
        }),
        invalidatesTags: ["Organizations"],
      }
    ),
    updateOrganization: build.mutation<
      Organization,
      { organizationId: string; data: UpdateOrganizationRequest }
    >({
      query: ({ organizationId, data }) => ({
        url: `/organizations/${organizationId}`,
        method: "PATCH",
        body: data,
      }),
      invalidatesTags: (_result, _error, { organizationId }) => [
        { type: "Organizations", id: organizationId },
        "Organizations",
      ],
    }),
    deleteOrganization: build.mutation<void, string>({
      query: (organizationId) => ({
        url: `/organizations/${organizationId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Organizations"],
    }),
    setCurrentOrganization: build.mutation<
      SetCurrentOrganizationResponse,
      SetCurrentOrganizationRequest
    >({
      query: (body) => ({
        url: "/organizations/current",
        method: "PUT",
        body,
      }),
      // Invalidate user data to refetch with updated currentOrganizationId
      invalidatesTags: ["Organizations"],
      // Invalidate all data that depends on organization/project
      async onQueryStarted(_, { dispatch, queryFulfilled }) {
        await queryFulfilled;
        dispatch(
          baseApi.util.invalidateTags([
            "Projects",
            "Workflows",
            "Credentials",
            "ChatSessions",
            "ApiKeys",
            "Executions",
            "ClientSessions",
            "Billing",
          ])
        );
      },
    }),
  }),
});

export const {
  useGetOrganizationsQuery,
  useGetOrganizationQuery,
  useCreateOrganizationMutation,
  useUpdateOrganizationMutation,
  useDeleteOrganizationMutation,
  useSetCurrentOrganizationMutation,
} = organizationApi;
