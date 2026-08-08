/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEPLOYMENT_LABEL?: string;
  readonly VITE_OIDC_CLIENT_ID?: string;
  readonly VITE_OIDC_ISSUER_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
