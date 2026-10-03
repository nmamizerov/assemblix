import type { VoiceOutputConfig } from "@/entities/voice-model";
import type { WorkflowAvatarConfig } from "@/entities/avatar-model";

export interface AgentInstruction {
  role: string;
  content: string;
}

export type VoiceAgentMode = "realtime" | "cascade";

// Each cascade block keeps unknown keys so a load → save round trip is lossless.
export interface CascadeSttConfig {
  provider: "yandex";
  model: string;
  credentialId: string | null;
  [key: string]: unknown;
}

export interface CascadeTurnConfig {
  minSilenceMs: number;
  maxSilenceMs: number;
  smartTurn: boolean;
  smartTurnThreshold: number;
  prerollMs: number;
  speculative: boolean;
  [key: string]: unknown;
}

export interface CascadeBrainConfig {
  type: "prompt";
  provider: string;
  model: string;
  credentialId: string | null;
  params: Record<string, unknown>;
  historyTurns: number;
  [key: string]: unknown;
}

export interface VoiceAgentCascadeConfig {
  stt: CascadeSttConfig;
  turn: CascadeTurnConfig;
  brain: CascadeBrainConfig;
  [key: string]: unknown;
}

export interface VoiceAgentConfig {
  instructions: AgentInstruction[];
  knowledgeBaseIds: string[];
  firstMessage: string | null;
  language: string;
  mode?: VoiceAgentMode;
  voice: VoiceOutputConfig | null;
  tts: VoiceOutputConfig | null;
  cascade?: VoiceAgentCascadeConfig | null;
  avatar: WorkflowAvatarConfig | null;
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
  mode: VoiceAgentMode;
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
  // null means no avatar is shown; the agent is voice/text only.
  avatar: WorkflowAvatarConfig | null;
  params: Record<string, unknown>;
  // Kept while editing a realtime agent too, so switching modes back and forth
  // does not lose it; only sent when mode is "cascade".
  cascade: VoiceAgentCascadeConfig;
  // Top-level config keys this UI does not know about.
  extraConfig: Record<string, unknown>;
  // Set on a realtime → cascade switch so switching back can restore the
  // realtime voice; never sent to the API.
  ttsBeforeCascade: {
    previous: VoiceOutputConfig | null;
    applied: VoiceOutputConfig | null;
  } | null;
}
