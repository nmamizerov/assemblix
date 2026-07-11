import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { WorkflowAvatarConfig } from "../../../model/types";

export type NodeStatus = "pending" | "running" | "completed" | "error";

export type EditorMode = "EDIT" | "DEBUG";

interface EditorModeState {
  mode: EditorMode;
  executionId: string | null;
  nodeStatuses: Record<string, NodeStatus>;
  isExecuting: boolean;
  // Static graph warnings, keyed by node id → i18n message key. Computed in the
  // editor from the graph structure (e.g. parallel END nodes, a join on a loop) and
  // rendered as an orange badge/border by BaseNode. Independent of execution status.
  nodeWarnings: Record<string, string>;
  // Workflow-global avatar persona for the current editor session. Seeded from
  // workflow.config.avatar and updated optimistically by the header so the picker
  // cascade and the agent-node warning react instantly (updateWorkflow does not
  // invalidate the workflow cache, so the prop alone would stay stale).
  avatarConfig: WorkflowAvatarConfig | null;
}

const initialState: EditorModeState = {
  mode: "EDIT",
  executionId: null,
  nodeStatuses: {},
  isExecuting: false,
  nodeWarnings: {},
  avatarConfig: null,
};

export const editorModeSlice = createSlice({
  name: "editorMode",
  initialState,
  reducers: {
    setEditorMode: (state, action: PayloadAction<EditorMode>) => {
      state.mode = action.payload;
      // При переключении в режим EDIT сбрасываем состояние выполнения
      if (action.payload === "EDIT") {
        state.executionId = null;
        state.nodeStatuses = {};
        state.isExecuting = false;
      }
    },
    setExecutionId: (state, action: PayloadAction<string | null>) => {
      state.executionId = action.payload;
    },
    updateNodeStatus: (
      state,
      action: PayloadAction<{ nodeId: string; status: NodeStatus }>
    ) => {
      state.nodeStatuses[action.payload.nodeId] = action.payload.status;
    },
    setIsExecuting: (state, action: PayloadAction<boolean>) => {
      state.isExecuting = action.payload;
    },
    resetExecution: (state) => {
      state.executionId = null;
      state.nodeStatuses = {};
      state.isExecuting = false;
    },
    clearNodeStatuses: (state) => {
      state.nodeStatuses = {};
    },
    setNodeWarnings: (
      state,
      action: PayloadAction<Record<string, string>>
    ) => {
      state.nodeWarnings = action.payload;
    },
    setAvatarConfig: (
      state,
      action: PayloadAction<WorkflowAvatarConfig | null>
    ) => {
      state.avatarConfig = action.payload;
    },
  },
});

export const {
  setEditorMode,
  setExecutionId,
  updateNodeStatus,
  setIsExecuting,
  resetExecution,
  clearNodeStatuses,
  setNodeWarnings,
  setAvatarConfig,
} = editorModeSlice.actions;

// Селекторы
export const selectEditorMode = (state: { editorMode: EditorModeState }) =>
  state.editorMode.mode;

export const selectNodeStatuses = (state: { editorMode: EditorModeState }) =>
  state.editorMode.nodeStatuses;

export const selectIsExecuting = (state: { editorMode: EditorModeState }) =>
  state.editorMode.isExecuting;

export const selectExecutionId = (state: { editorMode: EditorModeState }) =>
  state.editorMode.executionId;

export const selectNodeWarnings = (state: { editorMode: EditorModeState }) =>
  state.editorMode.nodeWarnings;

export const selectAvatarConfig = (state: { editorMode: EditorModeState }) =>
  state.editorMode.avatarConfig;

export const selectHasAvatarConfig = (state: {
  editorMode: EditorModeState;
}) =>
  Boolean(
    state.editorMode.avatarConfig?.avatarId &&
      state.editorMode.avatarConfig?.voiceId
  );
