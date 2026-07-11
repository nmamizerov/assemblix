# syntax=docker/dockerfile:1
# ============================================================================
# Assemblix docs image. Builds the MkDocs (Material) site from the repo-root
# `docs/` + `mkdocs.yml`, then serves the static HTML with nginx. The main web
# container proxies `/docs/` here, so the docs live under app-host/docs.
#
# Build context is the REPO ROOT (see docker-compose*.yml) so this Dockerfile
# can reach `docs/` and `mkdocs.yml`, which sit outside the web build context.
# ============================================================================

# --- build stage ------------------------------------------------------------
FROM python:3.13-slim AS build
WORKDIR /app

RUN pip install --no-cache-dir mkdocs-material

COPY mkdocs.yml .
COPY docs ./docs
RUN mkdocs build --strict -d /site

# --- serve stage ------------------------------------------------------------
FROM nginx:alpine AS prod
COPY docs-site/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /site /usr/share/nginx/html
EXPOSE 80
