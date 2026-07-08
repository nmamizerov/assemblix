export interface AvatarProviderListItem {
  name: string;
  label: string;
  modelsCount: number;
}

export interface AvatarModelMetadata {
  id: string;
  label: string;
  description?: string | null;
  avatarModel: string;
  costPerMinute?: number | null;
}

export interface AvatarListItem {
  id: string;
  name: string;
}

export interface AvatarSessionResponse {
  provider: string;
  sessionToken: string;
  videoConfig: Record<string, unknown>;
}

export interface WorkflowAvatarConfig {
  provider: string;
  avatarModel: string;
  avatarId?: string;
  voiceId?: string;
  // Display name of the selected voice, kept so the picker can still show it when
  // the voice isn't in the current (searched/paginated) results.
  voiceName?: string;
  credentialId?: string;
}
