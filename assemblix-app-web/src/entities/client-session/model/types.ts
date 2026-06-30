export interface ClientSession {
  id: string;
  projectId: string;
  clientId: string;
  state: Record<string, unknown>;
  metadata: Record<string, unknown>;
  executionCount: number;
  totalCredits: number;
  isActive: boolean;
  lastActivityAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface UpdateMetadataRequest {
  metadata: Record<string, unknown>;
}
