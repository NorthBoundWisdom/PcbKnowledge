ARG NODE_IMAGE=node:24.11.1-alpine
ARG NGINX_IMAGE=nginx:1.29.2-alpine

FROM ${NODE_IMAGE} AS build

WORKDIR /workspace
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/curator-web/package.json ./apps/curator-web/package.json
COPY packages/ui-kit/package.json ./packages/ui-kit/package.json
RUN pnpm install --frozen-lockfile

COPY apps/curator-web ./apps/curator-web
COPY packages/ui-kit ./packages/ui-kit

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_OIDC_ISSUER_URL
ARG VITE_OIDC_CLIENT_ID=pcbknowledge-curator-web
ARG VITE_DEPLOYMENT_LABEL="Local M0"
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_OIDC_ISSUER_URL=$VITE_OIDC_ISSUER_URL \
    VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID \
    VITE_DEPLOYMENT_LABEL=$VITE_DEPLOYMENT_LABEL

RUN test -n "$VITE_OIDC_ISSUER_URL" && pnpm build

FROM ${NGINX_IMAGE} AS runtime
COPY deploy/docker/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /workspace/apps/curator-web/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
