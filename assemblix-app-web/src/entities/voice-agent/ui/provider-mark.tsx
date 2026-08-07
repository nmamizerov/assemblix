import {
  CREDENTIAL_TYPE_CONFIG,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import { cn } from "@/shared/lib/utils";

interface ProviderMarkProps {
  provider: string;
  className?: string;
}

/**
 * The provider's own mark, reusing the icons the credentials manager already
 * ships. A voice provider maps to a credential type first, so a provider without
 * a matching key simply renders nothing rather than a placeholder box.
 */
export const ProviderMark = ({ provider, className }: ProviderMarkProps) => {
  const credentialType = getCredentialTypeForProvider(provider);
  if (!credentialType) return null;

  const { icon, label } = CREDENTIAL_TYPE_CONFIG[credentialType];
  return (
    <img
      src={icon}
      alt={label}
      aria-hidden
      className={cn("h-4 w-4 shrink-0 object-contain", className)}
    />
  );
};
