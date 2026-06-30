export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  ownerId: string;
  isPersonal: boolean;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CreateOrganizationRequest {
  name: string;
  slug?: string;
  description?: string;
}

export interface UpdateOrganizationRequest {
  name?: string;
  description?: string;
  isActive?: boolean;
}

export interface SetCurrentOrganizationRequest {
  organizationId: string;
}

export interface SetCurrentOrganizationResponse {
  currentOrganizationId: string;
  message: string;
}

export interface OrganizationMember {
  id: string;
  email: string;
  fullName?: string | null;
  isOwner: boolean;
  joinedAt: string;
}

export interface AddMemberRequest {
  email: string;
  isOwner?: boolean;
}
