import { createSlice, isAnyOf } from "@reduxjs/toolkit";
import type { StateVariable } from "./types";
import { workflowApi } from "../api/workflow.api";

interface VariablesState {
  // Словарь переменных по workflowId
  [workflowId: string]: StateVariable[];
}

const initialState: VariablesState = {};

export const variablesSlice = createSlice({
  name: "variables",
  initialState,
  reducers: {
    clearAllVariables: () => initialState,
  },
  extraReducers: (builder) => {
    builder.addMatcher(
      isAnyOf(
        workflowApi.endpoints.getWorkflow.matchFulfilled,
        workflowApi.endpoints.updateWorkflow.matchFulfilled
      ),
      (state, { payload }) => {
        state[payload.id] = payload.state || [];
      }
    );
  },
});

export const { clearAllVariables } = variablesSlice.actions;

// Селекторы
export const selectVariablesByWorkflowId = (
  state: { variables: VariablesState },
  workflowId: string
): StateVariable[] => {
  return state.variables[workflowId] || [];
};
