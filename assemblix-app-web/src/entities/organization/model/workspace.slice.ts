import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface WorkspaceState {
  currentOrganizationId: string | null;
  currentProjectId: string | null;
}

const initialState: WorkspaceState = {
  currentOrganizationId: localStorage.getItem("currentOrganizationId"),
  currentProjectId: localStorage.getItem("currentProjectId"),
};

export const workspaceSlice = createSlice({
  name: "workspace",
  initialState,
  reducers: {
    setCurrentOrganization: (state, action: PayloadAction<string>) => {
      state.currentOrganizationId = action.payload;
      // Reset project when organization changes
      state.currentProjectId = null;
      localStorage.setItem("currentOrganizationId", action.payload);
      localStorage.removeItem("currentProjectId");
    },
    setCurrentProject: (state, action: PayloadAction<string>) => {
      state.currentProjectId = action.payload;
      localStorage.setItem("currentProjectId", action.payload);
    },
    clearWorkspace: (state) => {
      state.currentOrganizationId = null;
      state.currentProjectId = null;
      localStorage.removeItem("currentOrganizationId");
      localStorage.removeItem("currentProjectId");
    },
  },
});

export const { setCurrentOrganization, setCurrentProject, clearWorkspace } =
  workspaceSlice.actions;

export const selectCurrentOrganizationId = (state: {
  workspace: WorkspaceState;
}) => state.workspace.currentOrganizationId;

export const selectCurrentProjectId = (state: { workspace: WorkspaceState }) =>
  state.workspace.currentProjectId;
