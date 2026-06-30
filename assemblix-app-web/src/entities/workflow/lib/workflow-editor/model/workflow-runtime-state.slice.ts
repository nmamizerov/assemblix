import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { StateVariable } from "@/entities/workflow/model/types";
import type { StateSchemaVariable } from "@/entities/project/model/types";

interface WorkflowRuntimeStateSlice {
  agentState: Record<string, unknown>;
  projectState: Record<string, unknown>;
  isStateDirty: boolean;
  lastUpdateTimestamp: number;
  // Ключи, которые поменялись в последнем applyExecutionUpdate (для flash)
  recentlyChangedAgentKeys: string[];
  recentlyChangedProjectKeys: string[];
}

const initialState: WorkflowRuntimeStateSlice = {
  agentState: {},
  projectState: {},
  isStateDirty: false,
  lastUpdateTimestamp: 0,
  recentlyChangedAgentKeys: [],
  recentlyChangedProjectKeys: [],
};

const isPlainObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

/**
 * Выравнивает структуру `current` по шаблону `template` (схеме defaultValue).
 * Сохраняет значения листьев из `current` там, где структура совпадает;
 * добавляет недостающие поля из `template`; удаляет поля, которых нет в `template`.
 */
const alignStructure = (current: unknown, template: unknown): unknown => {
  if (template === null || template === undefined) return current;

  if (Array.isArray(template)) {
    if (!Array.isArray(current)) return template;
    // Длина и форма элементов диктуются template, значения — из current
    return template.map((tItem, i) =>
      i < current.length ? alignStructure(current[i], tItem) : tItem,
    );
  }

  if (isPlainObject(template)) {
    if (!isPlainObject(current)) return template;
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(template)) {
      result[key] =
        key in current
          ? alignStructure(current[key], template[key])
          : template[key];
    }
    return result;
  }

  // Примитив — сохраняем то, что ввёл пользователь
  return current;
};

/**
 * Возвращает значение для переменной в merged state с учётом типа из схемы:
 * — если тип значения в state не соответствует схеме → берём default,
 * — если object → выравниваем структуру по default,
 * — иначе сохраняем то, что было.
 */
const reconcileValue = (
  schemaType: string,
  defaultValue: unknown,
  hasExisting: boolean,
  existingValue: unknown,
): unknown => {
  if (!hasExisting) return defaultValue;

  switch (schemaType) {
    case "object":
      return alignStructure(existingValue, defaultValue);
    case "string":
      return typeof existingValue === "string" ? existingValue : defaultValue;
    case "number":
      return typeof existingValue === "number" ? existingValue : defaultValue;
    case "boolean":
      return typeof existingValue === "boolean" ? existingValue : defaultValue;
    default:
      return existingValue;
  }
};

const diffChangedKeys = (
  prev: Record<string, unknown>,
  next: Record<string, unknown>,
): string[] => {
  const changed: string[] = [];
  for (const key of Object.keys(next)) {
    const a = prev[key];
    const b = next[key];
    if (a === b) continue;
    try {
      if (JSON.stringify(a) !== JSON.stringify(b)) changed.push(key);
    } catch {
      changed.push(key);
    }
  }
  return changed;
};

const getDefaultForType = (type: string): unknown => {
  switch (type) {
    case "string":
      return "";
    case "number":
      return 0;
    case "boolean":
      return false;
    case "object":
      return {};
    default:
      return null;
  }
};

const buildDefaults = <
  T extends { name: string; type: string; defaultValue?: unknown },
>(
  schema: T[] | undefined,
): Record<string, unknown> => {
  const result: Record<string, unknown> = {};
  if (!schema) return result;
  for (const v of schema) {
    result[v.name] =
      v.defaultValue !== undefined && v.defaultValue !== null
        ? v.defaultValue
        : getDefaultForType(v.type);
  }
  return result;
};

interface InitializePayload {
  workflowSchema?: StateVariable[];
  projectSchema?: StateSchemaVariable[];
}

interface ApplyExecutionUpdatePayload {
  agentState?: Record<string, unknown>;
  projectState?: Record<string, unknown>;
}

export const workflowRuntimeStateSlice = createSlice({
  name: "workflowRuntimeState",
  initialState,
  reducers: {
    initializeState: (
      state,
      action: PayloadAction<InitializePayload>,
    ) => {
      // Merge-режим: новые ключи получают defaults, существующие сохраняются,
      // удалённые из схемы — выкидываются. Для object-переменных структура
      // выравнивается по defaultValue (новые поля добавляются, удалённые
      // выкидываются), значения листьев сохраняются.
      const { workflowSchema, projectSchema } = action.payload;
      if (workflowSchema) {
        const defaults = buildDefaults(workflowSchema);
        const merged: Record<string, unknown> = {};
        for (const v of workflowSchema) {
          merged[v.name] = reconcileValue(
            v.type,
            defaults[v.name],
            v.name in state.agentState,
            state.agentState[v.name],
          );
        }
        state.agentState = merged;
      }
      if (projectSchema) {
        const defaults = buildDefaults(projectSchema);
        const merged: Record<string, unknown> = {};
        for (const v of projectSchema) {
          merged[v.name] = reconcileValue(
            v.type,
            defaults[v.name],
            v.name in state.projectState,
            state.projectState[v.name],
          );
        }
        state.projectState = merged;
      }
      state.recentlyChangedAgentKeys = [];
      state.recentlyChangedProjectKeys = [];
    },
    setAgentValue: (
      state,
      action: PayloadAction<{ key: string; value: unknown }>,
    ) => {
      state.agentState[action.payload.key] = action.payload.value;
      state.isStateDirty = true;
      state.recentlyChangedAgentKeys = [];
      state.recentlyChangedProjectKeys = [];
    },
    setProjectValue: (
      state,
      action: PayloadAction<{ key: string; value: unknown }>,
    ) => {
      state.projectState[action.payload.key] = action.payload.value;
      state.isStateDirty = true;
      state.recentlyChangedAgentKeys = [];
      state.recentlyChangedProjectKeys = [];
    },
    applyExecutionUpdate: (
      state,
      action: PayloadAction<ApplyExecutionUpdatePayload>,
    ) => {
      const agentChanged = action.payload.agentState
        ? diffChangedKeys(state.agentState, action.payload.agentState)
        : [];
      const projectChanged = action.payload.projectState
        ? diffChangedKeys(state.projectState, action.payload.projectState)
        : [];

      if (action.payload.agentState) {
        state.agentState = { ...state.agentState, ...action.payload.agentState };
      }
      if (action.payload.projectState) {
        state.projectState = {
          ...state.projectState,
          ...action.payload.projectState,
        };
      }
      state.lastUpdateTimestamp = Date.now();
      state.isStateDirty = false;
      state.recentlyChangedAgentKeys = agentChanged;
      state.recentlyChangedProjectKeys = projectChanged;
    },
    resetRuntimeState: (
      state,
      action: PayloadAction<InitializePayload>,
    ) => {
      const { workflowSchema, projectSchema } = action.payload;
      state.agentState = buildDefaults(workflowSchema);
      state.projectState = buildDefaults(projectSchema);
      state.isStateDirty = false;
      state.lastUpdateTimestamp = 0;
      state.recentlyChangedAgentKeys = [];
      state.recentlyChangedProjectKeys = [];
    },
  },
});

export const {
  initializeState,
  setAgentValue,
  setProjectValue,
  applyExecutionUpdate,
  resetRuntimeState,
} = workflowRuntimeStateSlice.actions;

export const selectAgentState = (state: {
  workflowRuntimeState: WorkflowRuntimeStateSlice;
}) => state.workflowRuntimeState.agentState;

export const selectProjectState = (state: {
  workflowRuntimeState: WorkflowRuntimeStateSlice;
}) => state.workflowRuntimeState.projectState;

export const selectIsStateDirty = (state: {
  workflowRuntimeState: WorkflowRuntimeStateSlice;
}) => state.workflowRuntimeState.isStateDirty;

export const selectLastUpdateTimestamp = (state: {
  workflowRuntimeState: WorkflowRuntimeStateSlice;
}) => state.workflowRuntimeState.lastUpdateTimestamp;

export const selectRecentlyChangedAgentKeys = (state: {
  workflowRuntimeState: WorkflowRuntimeStateSlice;
}) => state.workflowRuntimeState.recentlyChangedAgentKeys;

export const selectRecentlyChangedProjectKeys = (state: {
  workflowRuntimeState: WorkflowRuntimeStateSlice;
}) => state.workflowRuntimeState.recentlyChangedProjectKeys;
