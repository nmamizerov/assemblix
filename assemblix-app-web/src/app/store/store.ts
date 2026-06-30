import { configureStore } from "@reduxjs/toolkit";
import { setupListeners } from "@reduxjs/toolkit/query";
import { baseApi } from "@/shared/api";
import { sessionSlice } from "@/entities/session";
import { variablesSlice } from "@/entities/workflow/model/variables.slice";
import { credentialSlice } from "@/entities/credential/model/credential.slice";
import { editorModeSlice } from "@/entities/workflow/lib/workflow-editor/model/editor-mode.slice";
import { workflowRuntimeStateSlice } from "@/entities/workflow/lib/workflow-editor/model/workflow-runtime-state.slice";
import { workspaceSlice } from "@/entities/organization";
import { useDispatch } from "react-redux";

export const store = configureStore({
  reducer: {
    [baseApi.reducerPath]: baseApi.reducer,
    [sessionSlice.name]: sessionSlice.reducer,
    [variablesSlice.name]: variablesSlice.reducer,
    [credentialSlice.name]: credentialSlice.reducer,
    [editorModeSlice.name]: editorModeSlice.reducer,
    [workflowRuntimeStateSlice.name]: workflowRuntimeStateSlice.reducer,
    [workspaceSlice.name]: workspaceSlice.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(baseApi.middleware),
});

setupListeners(store.dispatch);

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Типизированный хук dispatch
export const useAppDispatch = () => useDispatch<AppDispatch>();
