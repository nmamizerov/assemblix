import { baseApi } from "@/shared/api/baseApi";
import type { Credential, CreateCredential } from "../model/types";

export type UpdateCredential = {
  id: string;
  name?: string | null;
  value?: string;
};

interface GetCredentialsParams {
  projectId: string;
}

export const credentialApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getCredentials: build.query<Credential[], GetCredentialsParams>({
      query: ({ projectId }) => ({
        url: "/credentials/",
        method: "GET",
        params: { project_id: projectId },
      }),
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ id }) => ({ type: "Credentials" as const, id })),
              { type: "Credentials", id: "LIST" },
            ]
          : [{ type: "Credentials", id: "LIST" }],
    }),
    createCredential: build.mutation<
      Credential,
      CreateCredential & { projectId: string }
    >({
      query: ({ projectId, ...credential }) => ({
        url: "/credentials/",
        method: "POST",
        body: { ...credential, project_id: projectId },
      }),
      invalidatesTags: [{ type: "Credentials", id: "LIST" }],
    }),
    updateCredential: build.mutation<Credential, UpdateCredential>({
      query: ({ id, ...patch }) => ({
        url: `/credentials/${id}`,
        method: "PATCH",
        body: patch,
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: "Credentials", id },
        { type: "Credentials", id: "LIST" },
      ],
    }),
    deleteCredential: build.mutation<void, string>({
      query: (id) => ({
        url: `/credentials/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, id) => [
        { type: "Credentials", id },
        { type: "Credentials", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetCredentialsQuery,
  useCreateCredentialMutation,
  useUpdateCredentialMutation,
  useDeleteCredentialMutation,
} = credentialApi;
