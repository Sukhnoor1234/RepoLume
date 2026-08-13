# ADR 0007: Render completed architecture artifacts with React Flow

- **Status:** Accepted
- **Date:** 2026-08-12

## Context

RepoLume already persists a versioned, language-neutral graph, but visitors
could only see analysis status. The first visualization must remain responsive,
distinguish confirmed evidence from heuristics, and let a visitor inspect the
source behind a node without making the landing page's initial bundle carry the
entire graph library.

## Decision

The web application renders completed schema `1.0` artifacts with React Flow
12.11.3. The explorer is loaded as a client-only dynamic component after a
valid completed artifact is available.

The first layout is deterministic: node kinds occupy fixed columns and retain
artifact order within each kind. Rendering is capped at 150 nodes, with a
visible truncation notice, while summaries continue to show full artifact
counts. Nodes are selectable but not draggable or connectable because this is
an evidence viewer rather than an architecture editor.

Before rendering, the client validates the artifact version, known kinds,
locations, IDs, edge endpoints, and collection counts. Confirmed and heuristic
edges receive different colors and line styles. The inspector displays
repository-relative source evidence without constructing a link to an
untrusted repository URL.

## Consequences

- A visitor can move from repository submission to a real explorable result in
  one interface.
- React Flow is isolated from the initial server-rendered page and sample map.
- The fixed-column layout is simple and reproducible but can become tall on
  large repositories.
- The 150-node cap protects browser interaction but does not yet provide graph
  search, clustering, or progressive expansion.
- ELK remains a planned option if later graphs require automatic hierarchical
  layout.
