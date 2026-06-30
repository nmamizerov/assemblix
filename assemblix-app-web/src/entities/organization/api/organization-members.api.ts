import { baseApi } from "@/shared/api/baseApi";
import type { OrganizationMember, AddMemberRequest } from "../model/types";

export const organizationMembersApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getOrganizationMembers: build.query<
      OrganizationMember[],
      { organizationId: string; skip?: number; limit?: number }
    >({
      query: ({ organizationId, skip = 0, limit = 100 }) => ({
        url: `/organizations/${organizationId}/members`,
        method: "GET",
        params: { skip, limit },
      }),
      providesTags: (_result, _error, { organizationId }) => [
        { type: "Organizations", id: `${organizationId}-members` },
      ],
    }),
    addOrganizationMember: build.mutation<
      OrganizationMember,
      { organizationId: string; data: AddMemberRequest }
    >({
      query: ({ organizationId, data }) => ({
        url: `/organizations/${organizationId}/members`,
        method: "POST",
        body: data,
      }),
      invalidatesTags: (_result, _error, { organizationId }) => [
        { type: "Organizations", id: `${organizationId}-members` },
      ],
    }),
    removeOrganizationMember: build.mutation<
      void,
      { organizationId: string; userId: string }
    >({
      query: ({ organizationId, userId }) => ({
        url: `/organizations/${organizationId}/members/${userId}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, { organizationId }) => [
        { type: "Organizations", id: `${organizationId}-members` },
      ],
    }),
  }),
});

export const {
  useGetOrganizationMembersQuery,
  useAddOrganizationMemberMutation,
  useRemoveOrganizationMemberMutation,
} = organizationMembersApi;
