import { baseApi } from "@/shared/api/baseApi";
import type {
  KnowledgeBase,
  KBDocument,
  KBDocumentDetail,
  CreateKBRequest,
  UpdateKBRequest,
  AddTextDocumentRequest,
} from "../model/types";

interface GetKBsParams {
  projectId: string;
}

interface GetKBDocumentsParams {
  knowledgeBaseId: string;
}

interface GetKBDocumentParams {
  knowledgeBaseId: string;
  documentId: string;
}

interface DeleteKBDocumentParams {
  knowledgeBaseId: string;
  documentId: string;
}

interface UploadPDFParams {
  knowledgeBaseId: string;
  formData: FormData;
}

export const knowledgeBaseApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getKnowledgeBases: build.query<KnowledgeBase[], GetKBsParams>({
      query: ({ projectId }) => ({
        url: "/knowledge-bases/",
        method: "GET",
        params: { project_id: projectId },
      }),
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ id }) => ({
                type: "KnowledgeBases" as const,
                id,
              })),
              { type: "KnowledgeBases", id: "LIST" },
            ]
          : [{ type: "KnowledgeBases", id: "LIST" }],
    }),

    getKnowledgeBase: build.query<KnowledgeBase, string>({
      query: (id) => ({
        url: `/knowledge-bases/${id}`,
        method: "GET",
      }),
      providesTags: (_result, _error, id) => [{ type: "KnowledgeBases", id }],
    }),

    createKnowledgeBase: build.mutation<KnowledgeBase, CreateKBRequest>({
      query: ({ projectId, ...body }) => ({
        url: "/knowledge-bases/",
        method: "POST",
        body: { ...body, project_id: projectId },
      }),
      invalidatesTags: [{ type: "KnowledgeBases", id: "LIST" }],
    }),

    updateKnowledgeBase: build.mutation<KnowledgeBase, UpdateKBRequest>({
      query: ({ id, ...patch }) => ({
        url: `/knowledge-bases/${id}`,
        method: "PATCH",
        body: patch,
      }),
      invalidatesTags: (_result, _error, { id }) => [
        { type: "KnowledgeBases", id },
        { type: "KnowledgeBases", id: "LIST" },
      ],
    }),

    deleteKnowledgeBase: build.mutation<void, string>({
      query: (id) => ({
        url: `/knowledge-bases/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, id) => [
        { type: "KnowledgeBases", id },
        { type: "KnowledgeBases", id: "LIST" },
      ],
    }),

    getKBDocuments: build.query<KBDocument[], GetKBDocumentsParams>({
      query: ({ knowledgeBaseId }) => ({
        url: `/knowledge-bases/${knowledgeBaseId}/documents`,
        method: "GET",
      }),
      providesTags: (result, _error, { knowledgeBaseId }) =>
        result
          ? [
              ...result.map(({ id }) => ({
                type: "KBDocuments" as const,
                id,
              })),
              { type: "KBDocuments", id: `LIST-${knowledgeBaseId}` },
            ]
          : [{ type: "KBDocuments", id: `LIST-${knowledgeBaseId}` }],
    }),

    getKBDocument: build.query<KBDocumentDetail, GetKBDocumentParams>({
      query: ({ knowledgeBaseId, documentId }) => ({
        url: `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
        method: "GET",
      }),
      providesTags: (_result, _error, { documentId }) => [
        { type: "KBDocuments", id: documentId },
      ],
    }),

    addTextDocument: build.mutation<KBDocument, AddTextDocumentRequest>({
      query: ({ knowledgeBaseId, ...body }) => ({
        url: `/knowledge-bases/${knowledgeBaseId}/documents/text`,
        method: "POST",
        body,
      }),
      invalidatesTags: (_result, _error, { knowledgeBaseId }) => [
        { type: "KBDocuments", id: `LIST-${knowledgeBaseId}` },
        { type: "KnowledgeBases", id: knowledgeBaseId },
        { type: "KnowledgeBases", id: "LIST" },
      ],
    }),

    uploadPDFDocument: build.mutation<KBDocument, UploadPDFParams>({
      query: ({ knowledgeBaseId, formData }) => ({
        url: `/knowledge-bases/${knowledgeBaseId}/documents/pdf`,
        method: "POST",
        body: formData,
        formData: true,
      }),
      invalidatesTags: (_result, _error, { knowledgeBaseId }) => [
        { type: "KBDocuments", id: `LIST-${knowledgeBaseId}` },
        { type: "KnowledgeBases", id: knowledgeBaseId },
        { type: "KnowledgeBases", id: "LIST" },
      ],
    }),

    deleteKBDocument: build.mutation<void, DeleteKBDocumentParams>({
      query: ({ knowledgeBaseId, documentId }) => ({
        url: `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
        method: "DELETE",
      }),
      invalidatesTags: (_result, _error, { knowledgeBaseId, documentId }) => [
        { type: "KBDocuments", id: documentId },
        { type: "KBDocuments", id: `LIST-${knowledgeBaseId}` },
        { type: "KnowledgeBases", id: knowledgeBaseId },
        { type: "KnowledgeBases", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetKnowledgeBasesQuery,
  useGetKnowledgeBaseQuery,
  useCreateKnowledgeBaseMutation,
  useUpdateKnowledgeBaseMutation,
  useDeleteKnowledgeBaseMutation,
  useGetKBDocumentsQuery,
  useGetKBDocumentQuery,
  useAddTextDocumentMutation,
  useUploadPDFDocumentMutation,
  useDeleteKBDocumentMutation,
} = knowledgeBaseApi;
