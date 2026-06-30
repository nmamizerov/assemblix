export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  documentCount: number;
  totalCharacters: number;
  maxCharacters: number;
  createdAt: string;
}

export interface KBDocument {
  id: string;
  name: string;
  type: "text" | "pdf";
  characterCount: number;
  createdAt: string;
}

export interface KBDocumentDetail extends KBDocument {
  content: string;
}

export interface CreateKBRequest {
  name: string;
  description?: string;
  projectId: string;
}

export interface UpdateKBRequest {
  id: string;
  name?: string;
  description?: string | null;
}

export interface AddTextDocumentRequest {
  knowledgeBaseId: string;
  name: string;
  content: string;
}
