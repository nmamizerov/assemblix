import type { VoiceOutputConfig } from "@/entities/voice-model";

export interface AgentInstruction {
  role: string;
  content: string;
}

export interface VoiceAgentConfig {
  instructions: AgentInstruction[];
  knowledgeBaseIds: string[];
  firstMessage: string | null;
  language: string;
  voice: VoiceOutputConfig;
  tts: VoiceOutputConfig | null;
  params: Record<string, unknown>;
  turnWorkflowId: string | null;
  finalWorkflowId: string | null;
}

export interface VoiceAgent {
  id: string;
  projectId: string;
  name: string;
  description: string | null;
  config: VoiceAgentConfig;
  isActive: boolean;
  sessionCount: number;
  totalCredits: number;
  ownKeyCostUsd: number;
  createdAt: string;
  updatedAt: string;
}

export interface CreateVoiceAgentRequest {
  projectId: string;
  name: string;
  description: string | null;
  config: VoiceAgentConfig;
}

export interface UpdateVoiceAgentRequest {
  id: string;
  name?: string;
  description?: string | null;
  config?: VoiceAgentConfig;
  isActive?: boolean;
}

export interface VoiceAgentDraft {
  name: string;
  description: string;
  systemPrompt: string;
  firstMessage: string;
  language: string;
  provider: string;
  model: string;
  voiceId: string;
  knowledgeBaseIds: string[];
  turnWorkflowId: string;
  finalWorkflowId: string;
  // Carried through untouched by the form so a load → save round trip does not
  // drop config the UI does not expose.
  credentialId: string | null;
  // null means the realtime model speaks with its own voice.
  tts: VoiceOutputConfig | null;
  params: Record<string, unknown>;
}
