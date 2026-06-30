export interface ServerConfig {
  /** Whether a system API key is configured per provider id (e.g. "openai"). */
  systemApiKeys: Record<string, boolean>;
  /** Whether paid billing/payments are enabled on this server. */
  billingEnabled: boolean;
}
