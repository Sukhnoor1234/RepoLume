"use client";

import { useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
} from "@xyflow/react";
import type { Edge, Node, NodeProps } from "@xyflow/react";

import type {
  ArchitectureNode,
  ArchitectureNodeKind,
  RepositoryArchitecture,
} from "@/app/lib/architecture-contract";

const MAXIMUM_VISIBLE_NODES = 150;
const KIND_ORDER: Record<ArchitectureNodeKind, number> = {
  repository: 0,
  module: 1,
  entry_point: 2,
  external_dependency: 3,
  symbol: 4,
};
const KIND_COLUMN: Record<ArchitectureNodeKind, number> = {
  repository: 0,
  module: 220,
  symbol: 440,
  entry_point: 440,
  external_dependency: 440,
};

type ExplorerNodeData = {
  architectureNode: ArchitectureNode;
};
type ExplorerFlowNode = Node<ExplorerNodeData, "architecture">;

function ArchitectureNodeCard({ data, selected }: NodeProps<ExplorerFlowNode>) {
  const node = data.architectureNode;
  return (
    <div className={`explorer-node explorer-node-${node.kind}${selected ? " is-selected" : ""}`}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span>{node.kind.replaceAll("_", " ")}</span>
      <strong>{node.name}</strong>
      {node.language ? <small>{node.language}</small> : null}
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const NODE_TYPES = { architecture: ArchitectureNodeCard } as const;

function buildFlow(architecture: RepositoryArchitecture) {
  const visibleArchitectureNodes = [...architecture.nodes]
    .sort((left, right) => KIND_ORDER[left.kind] - KIND_ORDER[right.kind])
    .slice(0, MAXIMUM_VISIBLE_NODES);
  const rowByColumn = new Map<number, number>();
  const visibleIds = new Set(visibleArchitectureNodes.map((node) => node.id));
  const nodes: ExplorerFlowNode[] = visibleArchitectureNodes.map((node) => {
    const column = KIND_COLUMN[node.kind];
    const row = rowByColumn.get(column) ?? 0;
    rowByColumn.set(column, row + 1);
    return {
      id: node.id,
      type: "architecture",
      position: { x: column, y: row * 112 },
      data: { architectureNode: node },
      draggable: false,
      connectable: false,
      ariaLabel: `${node.kind.replaceAll("_", " ")}: ${node.name}`,
    };
  });
  const edges: Edge[] = architecture.edges
    .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    .map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      label: edge.kind === "depends_on" ? "depends" : undefined,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke: edge.confidence === "confirmed" ? "#53d6e8" : "#f1bd70",
        strokeDasharray: edge.confidence === "heuristic" ? "6 5" : undefined,
      },
    }));
  return { nodes, edges, truncated: architecture.nodes.length > nodes.length };
}

function countLabel(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export default function ArchitectureExplorer({
  architecture,
}: {
  architecture: RepositoryArchitecture;
}) {
  const flow = useMemo(() => buildFlow(architecture), [architecture]);
  const [selectedId, setSelectedId] = useState(
    () => flow.nodes.find((node) => node.data.architectureNode.kind === "repository")?.id ?? flow.nodes[0]?.id,
  );
  const selected = architecture.nodes.find((node) => node.id === selectedId) ?? null;
  const selectedEdges = selected
    ? architecture.edges.filter((edge) => edge.source === selected.id || edge.target === selected.id)
    : [];
  const renderedNodes = useMemo(
    () => flow.nodes.map((node) => ({ ...node, selected: node.id === selectedId })),
    [flow.nodes, selectedId],
  );

  return (
    <>
      <div className="map-header explorer-header">
        <div>
          <span className="map-kicker">Live architecture</span>
          <h2>{architecture.languages.join(" + ") || "Repository graph"}</h2>
        </div>
        <span className="analysis-status">{architecture.summary.nodeCount} nodes</span>
      </div>

      <div className="explorer-summary" aria-label="Architecture summary">
        <span>{countLabel(architecture.summary.moduleCount, "module")}</span>
        <span>{countLabel(architecture.summary.symbolCount, "symbol")}</span>
        <span>{countLabel(architecture.summary.dependencyCount, "dependency", "dependencies")}</span>
        <span>{countLabel(architecture.summary.entryPointCount, "entry point")}</span>
      </div>

      <div className="live-map-shell">
        <div className="react-flow-region" aria-label="Interactive architecture graph">
          <ReactFlow
            nodes={renderedNodes}
            edges={flow.edges}
            nodeTypes={NODE_TYPES}
            onNodeClick={(_event, node) => setSelectedId(node.id)}
            nodesConnectable={false}
            nodesDraggable={false}
            elementsSelectable
            deleteKeyCode={null}
            fitView
            fitViewOptions={{ padding: 0.18, maxZoom: 1.15 }}
            minZoom={0.12}
            maxZoom={1.8}
            colorMode="dark"
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#284454" />
            <MiniMap
              pannable
              zoomable
              nodeColor={(node) =>
                node.data?.architectureNode.kind === "external_dependency" ? "#f1bd70" : "#53d6e8"
              }
            />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        <aside className="node-inspector" aria-live="polite">
          {selected ? (
            <>
              <span className="map-kicker">Selected {selected.kind.replaceAll("_", " ")}</span>
              <h3>{selected.name}</h3>
              {selected.qualifiedName && selected.qualifiedName !== selected.name ? (
                <p>{selected.qualifiedName}</p>
              ) : selected.language ? <p>{selected.language}</p> : null}
              {selected.detail ? <p>{selected.detail}</p> : null}
              <dl>
                <div><dt>Relationships</dt><dd>{selectedEdges.length}</dd></div>
                <div><dt>Confidence</dt><dd>{selected.confidence ?? "confirmed"}</dd></div>
                {selected.symbolKind ? <div><dt>Symbol</dt><dd>{selected.symbolKind.replaceAll("_", " ")}</dd></div> : null}
                {selected.lineCount !== null ? <div><dt>Lines</dt><dd>{selected.lineCount}</dd></div> : null}
              </dl>
              {selected.decorators.length > 0 ? (
                <p>Decorators: {selected.decorators.join(", ")}</p>
              ) : null}
              {selected.location ? (
                <code>{selected.location.path}:{selected.location.line}
                  {selected.location.endLine !== selected.location.line
                    ? `–${selected.location.endLine}`
                    : ""}
                </code>
              ) : (
                <p className="node-inspector-empty">No source location for this node.</p>
              )}
            </>
          ) : (
            <p className="node-inspector-empty">Select a node to inspect its source evidence.</p>
          )}
          {flow.truncated ? (
            <p className="graph-limit-note">
              Showing {MAXIMUM_VISIBLE_NODES} of {architecture.nodes.length} nodes for browser performance.
            </p>
          ) : null}
        </aside>
      </div>
    </>
  );
}
