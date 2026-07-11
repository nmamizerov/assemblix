export enum CredentialType {
  OPENAI_TOKEN = "openai_token",
  GEMINI_TOKEN = "gemini_token",
  DEEPSEEK_TOKEN = "deepseek_token",
  ELEVENLABS_TOKEN = "elevenlabs_token",
  ANAM_TOKEN = "anam_token",
  YANDEX_SPEECHKIT_TOKEN = "yandex_speechkit_token",
}

export type Credential = {
  id: string;
  type: CredentialType;
  name: string | null;
  createdAt: string;
  updatedAt: string;
};

export type CreateCredential = {
  type: CredentialType;
  name: string | null;
  value: string;
};
