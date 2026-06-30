import { CredentialType } from "./types";
import OpenAIIcon from "../assets/openai.svg";
import GeminiIcon from "../assets/google.svg";
import DeepSeekIcon from "../assets/deepseek.svg";
import GigachatIcon from "../assets/gigachat.svg";

export interface CredentialTypeConfigItem {
  type: CredentialType;
  label: string;
  icon: string;
  color: string;
}

export const CREDENTIAL_TYPE_CONFIG: Record<
  CredentialType,
  CredentialTypeConfigItem
> = {
  [CredentialType.OPENAI_TOKEN]: {
    type: CredentialType.OPENAI_TOKEN,
    label: "OpenAI Token",
    icon: OpenAIIcon,
    color: "text-emerald-600",
  },
  [CredentialType.GEMINI_TOKEN]: {
    type: CredentialType.GEMINI_TOKEN,
    label: "Gemini Token",
    icon: GeminiIcon,
    color: "text-indigo-600",
  },
  [CredentialType.DEEPSEEK_TOKEN]: {
    type: CredentialType.DEEPSEEK_TOKEN,
    label: "DeepSeek Token",
    icon: DeepSeekIcon,
    color: "text-purple-600",
  },
  [CredentialType.GIGACHAT_TOKEN]: {
    type: CredentialType.GIGACHAT_TOKEN,
    label: "GigaChat Token",
    icon: GigachatIcon,
    color: "text-purple-700",
  },
};

/**
 * Получить список всех доступных типов credentials
 */
export const getAllCredentialTypes = (): CredentialTypeConfigItem[] => {
  return Object.values(CREDENTIAL_TYPE_CONFIG);
};
