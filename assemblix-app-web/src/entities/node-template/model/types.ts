export interface NodeTemplateConfig {
  id: string;
  type: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;
}

export interface NodeTemplate {
  id: string;
  projectId: string;
  name: string;
  description: string | null;
  config: NodeTemplateConfig;
  createdAt: string;
  updatedAt: string;
}

export interface CreateNodeTemplateRequest {
  projectId: string;
  name: string;
  description?: string;
  config: NodeTemplateConfig;
}

export interface UpdateNodeTemplateRequest {
  name?: string;
  description?: string;
  config?: NodeTemplateConfig;
}
