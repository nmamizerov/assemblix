/**
 * Custom-widget registry: node type → bespoke form component.
 *
 * Register here any node type whose configuration form is too complex or
 * context-sensitive to be data-driven by a NodeDescriptor alone.
 * The dispatcher in nodeEditor.tsx checks this map first; if the type is absent,
 * it falls through to <GenericNodeForm>.
 *
 * Scope (conservative):
 *   agent       — multi-tab form with credential/model/tool/KB selectors, CEL editor.
 *   end         — collapsible advanced section with CEL, multi-select, agent-node selector.
 *   set_variable — dynamic update-variable list with type-aware value pickers.
 *   http_request — raw headers/body/query-params editing, credential selection.
 *
 * start / sticker / condition are kept as custom widgets because:
 *   - start: also manages workflow-level state variables (not part of node config).
 *   - condition: uses a custom CEL textarea with variable suggestions popover.
 *   - sticker: trivially simple but kept for symmetry with the test harness that
 *              already tests StickerNodeForm directly.
 */
import type { ComponentType } from "react";
import { AgentNodeForm } from "../agent-node-form";
import { EndNodeForm } from "../end-node-form";
import { SetVariableNodeForm } from "../set-variable-node-form";
import { HTTPRequestNodeForm } from "../http-request-node-form";
import { StartNodeForm } from "../start-node-form";
import { StickerNodeForm } from "../sticker-node-form";
import { ConditionNodeForm } from "../condition-node-form";

// Shared props subset that every custom widget must accept.
// The dispatcher passes these from nodeEditor.tsx.
export interface NodeFormProps {
  nodeId: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config?: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  workflow?: any;
  projectId?: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const customWidgets: Record<string, ComponentType<any>> = {
  agent: AgentNodeForm,
  end: EndNodeForm,
  set_variable: SetVariableNodeForm,
  http_request: HTTPRequestNodeForm,
  start: StartNodeForm,
  sticker: StickerNodeForm,
  condition: ConditionNodeForm,
};
