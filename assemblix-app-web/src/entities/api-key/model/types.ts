export type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  isActive: boolean;
  lastUsedAt: string | null;
  requestCount: number;
  createdAt: string;
  updatedAt: string;
};

export type ApiKeyWithSecret = {
  id: string;
  name: string;
  apiKey: string;
  prefix: string;
  createdAt: string;
};

export type CreateApiKeyRequest = {
  name: string;
};

export type GetApiKeysResponse = {
  keys: ApiKey[];
  total: number;
};
