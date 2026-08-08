export type RouteGroup = "Operate" | "Curate" | "Assure" | "Control";

export interface FoundationRouteDefinition {
  description: string;
  group: RouteGroup;
  milestone: "M0" | "M1" | "M2" | "M3" | "M4" | "M5";
  path: string;
  title: string;
}

export const foundationRoutes = {
  admin: {
    description: "Administration landing page for source, policy, schema, and access controls.",
    group: "Control",
    milestone: "M1",
    path: "/admin",
    title: "Administration",
  },
  audit: {
    description: "Read-only exploration of append-only access, review, publication, and system events.",
    group: "Assure",
    milestone: "M1",
    path: "/audit",
    title: "Audit explorer",
  },
  dashboard: {
    description: "Operational entry point for intake, review, conflict, failure, and platform readiness signals.",
    group: "Operate",
    milestone: "M1",
    path: "/dashboard",
    title: "Dashboard",
  },
  documentDetail: {
    description: "Revision metadata, immutable source evidence, pages, derived assets, and revision history.",
    group: "Operate",
    milestone: "M2",
    path: "/documents/:revisionId",
    title: "Document revision",
  },
  documents: {
    description: "Evidence Vault catalog for documents, immutable revisions, parsing state, and source policy.",
    group: "Operate",
    milestone: "M2",
    path: "/documents",
    title: "Documents",
  },
  entities: {
    description: "Browse manufacturers, components, orderable parts, packages, pins, and aliases without conflation.",
    group: "Curate",
    milestone: "M3",
    path: "/entities",
    title: "Entities",
  },
  entityResolver: {
    description: "Human confirmation surface for ambiguous identifiers, packages, revisions, and merge candidates.",
    group: "Curate",
    milestone: "M3",
    path: "/entities/resolve",
    title: "Entity resolver",
  },
  evals: {
    description: "Repeatable extraction, retrieval, permission, and publication regression evidence.",
    group: "Assure",
    milestone: "M5",
    path: "/evals",
    title: "Evaluation center",
  },
  intake: {
    description: "Track approved source submissions before immutable ingestion and parsing begin.",
    group: "Operate",
    milestone: "M2",
    path: "/intake",
    title: "Intake inbox",
  },
  intakeNew: {
    description: "Five-step source, license, document identity, entity binding, and confirmation workflow.",
    group: "Operate",
    milestone: "M2",
    path: "/intake/new",
    title: "New document intake",
  },
  jobs: {
    description: "Monitor leased PostgreSQL work, retries, idempotency, and dead-letter outcomes.",
    group: "Control",
    milestone: "M1",
    path: "/jobs",
    title: "Job monitor",
  },
  knowledge: {
    description: "Explore typed published records, immutable versions, applicability, conflict, and evidence chains.",
    group: "Curate",
    milestone: "M4",
    path: "/knowledge",
    title: "Knowledge explorer",
  },
  knowledgeDetail: {
    description: "Inspect one stable knowledge identity and its immutable versions, evidence, and review history.",
    group: "Curate",
    milestone: "M4",
    path: "/knowledge/:recordId",
    title: "Knowledge record",
  },
  review: {
    description: "Prioritized curator and domain-review tasks with explicit permission and risk boundaries.",
    group: "Operate",
    milestone: "M3",
    path: "/review",
    title: "Review queue",
  },
  reviewWorkbench: {
    description: "Evidence page rail, PDF canvas, record inspector, and auditable review decision dock.",
    group: "Operate",
    milestone: "M3",
    path: "/review/:taskId",
    title: "Review workbench",
  },
  search: {
    description: "Evidence discovery with exact filters, permission-first retrieval, and explicit unknown results.",
    group: "Curate",
    milestone: "M4",
    path: "/search",
    title: "Evidence search",
  },
  sources: {
    description: "Govern source organizations, license policies, and permitted processing scopes.",
    group: "Control",
    milestone: "M1",
    path: "/admin/sources",
    title: "Sources and licenses",
  },
} as const satisfies Record<string, FoundationRouteDefinition>;
