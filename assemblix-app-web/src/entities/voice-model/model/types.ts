export interface VoiceProviderListItem {
  name: string; // stable id, e.g. "openai"
  label: string; // human label
  modelsCount: number;
}

export type VoiceCapability = "transcription" | "speech" | "realtime";

export interface VoiceModelMetadata {
  id: string;
  label: string;
  description?: string | null;
  capability: VoiceCapability;
  route: "transcription" | "completion";
  costPerMinute?: number | null;
}
