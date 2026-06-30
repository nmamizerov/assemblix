import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type NodeStatus = "pending" | "running" | "completed" | "error";

export type EditorMode = "EDIT" | "DEBUG";

interface EditorModeState {
  mode: EditorMode;
  executionId: string | null;
  nodeStatuses: Record<string, NodeStatus>;
  isExecuting: boolean;
}

const initialState: EditorModeState = {
  mode: "EDIT",
  executionId: null,
  nodeStatuses: {},
  isExecuting: false,
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
  },
});

export const {
  setEditorMode,
  setExecutionId,
  updateNodeStatus,
  setIsExecuting,
  resetExecution,
  clearNodeStatuses,
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
