# ADR-006: Fix the curator frontend stack

## Status

Accepted — 2026-08-08.

## Context

The review workbench needs dense lists, recoverable URLs, typed server state, and a precise PDF evidence overlay. A consistent stack reduces UI and contract drift.

## Decision

Use Node.js 24 LTS, pnpm, React 19, TypeScript, Vite 8, Material UI 9, React Router 7, TanStack Query/Table/Virtual, Zustand for local UI state, React Hook Form with Zod, and PDF.js 6. API clients are generated from OpenAPI; components do not call `fetch` directly.

## Alternatives

- Server-rendered templates.
- Next.js as a full-stack runtime.
- Tailwind or MUI X Pro for core workflows.
- A black-box hosted PDF viewer.

## Consequences

The workbench has explicit state ownership and can render native evidence overlays. The dependency surface is substantial and requires lockfile, build, accessibility, and screenshot regression discipline.

## Rollback

Replace a layer only through a superseding ADR and compatibility plan that preserves URLs, generated contracts, evidence coordinates, accessibility, and critical Playwright flows.
