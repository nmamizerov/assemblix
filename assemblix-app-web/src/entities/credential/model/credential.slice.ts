import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

interface CredentialModalState {
  isOpen: boolean;
  editingId: string | "new" | null; // ID редактируемого credential, "new" для создания, null = просмотр
  deletingId: string | null; // ID credential для удаления
  onCreatedCallback?: (credentialId: string) => void; // Callback после создания
}

const initialState: CredentialModalState = {
  isOpen: false,
  editingId: null,
  deletingId: null,
  onCreatedCallback: undefined,
};

export const credentialSlice = createSlice({
  name: "credentialModal",
  initialState,
  reducers: {
    openModal: (
      state,
      action: PayloadAction<((credentialId: string) => void) | undefined>
    ) => {
      state.isOpen = true;
      state.onCreatedCallback = action.payload;
    },
    closeModal: (state) => {
      state.isOpen = false;
      state.editingId = null;
      state.deletingId = null;
      state.onCreatedCallback = undefined;
    },
    startEditing: (state, action: PayloadAction<string>) => {
      state.editingId = action.payload;
      state.deletingId = null;
    },
    startCreating: (state) => {
      state.editingId = "new";
      state.deletingId = null;
    },
    cancelEditing: (state) => {
      state.editingId = null;
    },
    startDeleting: (state, action: PayloadAction<string>) => {
      state.deletingId = action.payload;
      state.editingId = null;
    },
    cancelDeleting: (state) => {
      state.deletingId = null;
    },
  },
});

export const {
  openModal,
  closeModal,
  startEditing,
  startCreating,
  cancelEditing,
  startDeleting,
  cancelDeleting,
} = credentialSlice.actions;

// Selectors
export const selectIsOpen = (state: {
  credentialModal: CredentialModalState;
}) => state.credentialModal.isOpen;

export const selectEditingId = (state: {
  credentialModal: CredentialModalState;
}) => state.credentialModal.editingId;

export const selectDeletingId = (state: {
  credentialModal: CredentialModalState;
}) => state.credentialModal.deletingId;

export const selectOnCreatedCallback = (state: {
  credentialModal: CredentialModalState;
}) => state.credentialModal.onCreatedCallback;
