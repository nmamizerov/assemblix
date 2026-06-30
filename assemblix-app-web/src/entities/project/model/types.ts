export interface StateSchemaVariable {
  name: string;
  defaultValue: unknown;
  type: "string" | "number" | "boolean" | "object";
}

export interface Project {
  id: string;
  organizationId: string;
  name: string;
  slug: string;
  description?: string | null;
  isActive: boolean;
  stateSchema?: StateSchemaVariable[];
  createdAt: string;
  updatedAt: string;
}

export interface CreateProjectRequest {
  name: string;
  slug?: string;
  description?: string;
}

export interface UpdateProjectRequest {
  name?: string;
  slug?: string;
  description?: string;
  isActive?: boolean;
  stateSchema?: StateSchemaVariable[];
}
