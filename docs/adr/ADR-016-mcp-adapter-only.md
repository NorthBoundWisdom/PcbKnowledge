# ADR-016: Keep MCP as an adapter

## Status

Deferred — MCP integration is a P2 capability.

## Context

Agents need programmable knowledge access, but coupling domain semantics to one tool transport would make internal modules and non-agent clients depend on MCP evolution.

## Decision

Typed REST/OpenAPI remains the public domain contract. A future separately deployed MCP adapter may translate a bounded tool catalog to those APIs. It has no database access, independent facts, board mutation tools, or authorization bypass.

## Alternatives

- Use MCP as the internal service protocol.
- Implement only a generic `ask_documents` tool.
- Give the adapter direct database access.

## Consequences

Web, automation, and agents share one versioned contract and transport adapters remain replaceable. MCP adds another deployment and mapping layer when P2 begins.

## Rollback

Remove or disable the adapter without changing knowledge data or REST clients. Agents can use the typed REST API through their existing harness.
