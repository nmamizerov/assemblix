# syntax=docker/dockerfile:1
# ============================================================================
# Assemblix web image. Multi-stage: build the Vite SPA with Node, then serve
# the static bundle with nginx (which also proxies /api -> the api service).
# VITE_* values are baked in at build time via build args.
# ============================================================================

# --- build stage ------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

# Install deps first (cached unless package.json / yarn.lock change).
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

# Build-time config (only VITE_-prefixed vars reach the client bundle).
ARG VITE_API_BASE_URL=/api
ARG VITE_APP_VERSION=1.0.0
ARG VITE_LANGS=ru,en
ARG VITE_DEFAULT_LANGUAGE=ru
ARG VITE_SUPPORTED_LANGUAGES=ru,en
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_GITHUB_CLIENT_ID=
ARG VITE_YANDEX_CLIENT_ID=
ARG VITE_PADDLE_CLIENT_TOKEN=
ARG VITE_PADDLE_ENVIRONMENT=production
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_APP_VERSION=$VITE_APP_VERSION \
    VITE_LANGS=$VITE_LANGS \
    VITE_DEFAULT_LANGUAGE=$VITE_DEFAULT_LANGUAGE \
    VITE_SUPPORTED_LANGUAGES=$VITE_SUPPORTED_LANGUAGES \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_GITHUB_CLIENT_ID=$VITE_GITHUB_CLIENT_ID \
    VITE_YANDEX_CLIENT_ID=$VITE_YANDEX_CLIENT_ID \
    VITE_PADDLE_CLIENT_TOKEN=$VITE_PADDLE_CLIENT_TOKEN \
    VITE_PADDLE_ENVIRONMENT=$VITE_PADDLE_ENVIRONMENT

RUN yarn build

# --- serve stage ------------------------------------------------------------
FROM nginx:alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
