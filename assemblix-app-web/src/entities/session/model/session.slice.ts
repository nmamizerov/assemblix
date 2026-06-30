import { createSlice, isAnyOf } from "@reduxjs/toolkit";
import { authApi } from "../api/auth.api";

interface SessionState {
  accessToken: string | null;
  isAuthorized: boolean;
}

const initialState: SessionState = {
  accessToken: localStorage.getItem("accessToken"),
  isAuthorized: !!localStorage.getItem("accessToken"),
};

export const sessionSlice = createSlice({
  name: "session",
  initialState,
  reducers: {
    logout: (state) => {
      state.accessToken = null;
      state.isAuthorized = false;
      localStorage.removeItem("accessToken");
    },
  },
  extraReducers: (builder) => {
    builder
      .addMatcher(
        isAnyOf(
          authApi.endpoints.login.matchFulfilled,
          authApi.endpoints.register.matchFulfilled,
          authApi.endpoints.googleOAuth.matchFulfilled,
          authApi.endpoints.githubOAuth.matchFulfilled
        ),
        (state, { payload }) => {
          state.accessToken = payload.accessToken;
          state.isAuthorized = true;
          localStorage.setItem("accessToken", payload.accessToken);
        }
      )
      .addMatcher(
        authApi.endpoints.registerOrLogin.matchFulfilled,
        (state, { payload }) => {
          if (payload.accessToken) {
            state.accessToken = payload.accessToken;
            state.isAuthorized = true;
            localStorage.setItem("accessToken", payload.accessToken);
          }
        }
      )
      .addMatcher(
        (action) =>
          action.type.endsWith("/rejected") && action.payload?.status === 401,
        (state) => {
          state.accessToken = null;
          state.isAuthorized = false;
          localStorage.removeItem("accessToken");
        }
      );
  },
});

export const { logout } = sessionSlice.actions;

export const selectIsAuthorized = (state: { session: SessionState }) =>
  state.session.isAuthorized;

export const selectAccessToken = (state: { session: SessionState }) =>
  state.session.accessToken;
