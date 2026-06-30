export interface RegisterRequest {
  email: string;
  password: string;
  fullName?: string | null;
  companyName?: string | null;
  utmSource?: string;
  utmMedium?: string;
  utmCampaign?: string;
  utmContent?: string;
  utmTerm?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  accessToken: string;
}

export interface UserOnboarding {
  seenWelcome?: boolean;
  tourCompleted?: boolean;
  tourStep?: number;
  completedSteps?: string[];
}

export interface User {
  id: string;
  email: string;
  fullName?: string | null;
  companyName?: string | null;
  isActive: boolean;
  isVerified: boolean;
  currentOrganizationId?: string | null;
  onboarding?: UserOnboarding;
}

export interface UpdateUserRequest {
  fullName?: string;
  companyName?: string;
  onboarding?: Partial<UserOnboarding>;
}

export interface GoogleOAuthRequest {
  idToken: string;
}

export interface GithubOAuthRequest {
  idToken: string;
}

export interface RegisterOrLoginRequest {
  email: string;
  password: string;
  fullName?: string | null;
  companyName?: string | null;
  utmSource?: string;
  utmMedium?: string;
  utmCampaign?: string;
  utmContent?: string;
  utmTerm?: string;
}

export interface RegisterOrLoginResponse {
  action: "registered" | "logged_in" | "account_exists" | "oauth_account";
  accessToken: string | null;
  tokenType: string;
  expiresIn: number | null;
  organizationId: string | null;
  projectId: string | null;
  provider: string | null;
}
