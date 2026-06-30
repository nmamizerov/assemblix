import { baseApi } from "@/shared/api/baseApi";
import type {
  LoginRequest,
  RegisterRequest,
  RegisterOrLoginRequest,
  RegisterOrLoginResponse,
  TokenResponse,
  User,
  UpdateUserRequest,
  GoogleOAuthRequest,
  GithubOAuthRequest,
} from "../model/types";

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    register: build.mutation<TokenResponse, RegisterRequest>({
      query: (body) => ({
        url: "/auth/register",
        method: "POST",
        body,
      }),
    }),
    login: build.mutation<TokenResponse, LoginRequest>({
      query: (body) => ({
        url: "/auth/login",
        method: "POST",
        body,
      }),
    }),
    googleOAuth: build.mutation<TokenResponse, GoogleOAuthRequest>({
      query: (body) => ({
        url: "/auth/oauth/google",
        method: "POST",
        body,
      }),
    }),
    githubOAuth: build.mutation<TokenResponse, GithubOAuthRequest>({
      query: (body) => ({
        url: "/auth/oauth/github",
        method: "POST",
        body,
      }),
    }),
    registerOrLogin: build.mutation<RegisterOrLoginResponse, RegisterOrLoginRequest>({
      query: (body) => ({
        url: "/auth/register-or-login",
        method: "POST",
        body,
      }),
    }),
    me: build.query<User, void>({
      query: () => ({
        url: "/auth/me",
        method: "GET",
      }),
    }),
    updateMe: build.mutation<User, UpdateUserRequest>({
      query: (body) => ({
        url: "/auth/me",
        method: "PATCH",
        body,
      }),
      async onQueryStarted(_, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled;
        dispatch(authApi.util.updateQueryData("me", undefined, () => data));
      },
    }),
  }),
});

export const {
  useRegisterMutation,
  useLoginMutation,
  useGoogleOAuthMutation,
  useGithubOAuthMutation,
  useRegisterOrLoginMutation,
  useMeQuery,
  useUpdateMeMutation,
} = authApi;
