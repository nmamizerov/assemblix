import type { Workflow } from "@/entities/workflow";

export interface ChatSession {
  id: string;
  name: string | null;
  workflowId: string;
  workflow: Workflow;
  userId: string;
  totalCredits: number;
  isActive: boolean;
  lastMessageAt: string | null;
  messageCount: number;
  createdAt: string;
}

export interface Message {
  id: string;
  chatSessionId: string;
  executionId: string | null;
  role: "user" | "assistant";
  content: string;
  metaData: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface ChatSessionDetail extends ChatSession {
  updatedAt: string;
  currentState: Record<string, unknown>;
  messages: Message[];
}
