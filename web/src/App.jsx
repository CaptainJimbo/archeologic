import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { marked } from "marked";

// --- type + relation visual grammar -------------------------------------
const TYPE_COLOR = {
  claim: "#f0b429", // amber  — assertions under investigation
  source: "#38bdf8", // cyan   — fetched documents (evidence)
  site: "#34d399", // green  — places
  scholar: "#a78bfa", // violet — people who argue
};
const TYPE_LABEL = {
  claim: "Claim",
  source: "Source",
  site: "Site",
  scholar: "Scholar",
};
const REL_STYLE = {
  supports: { color: "#4ea88a", dash: null, arrow: true },
  disputes: { color: "#f0506e", dash: [5, 4], arrow: true },
  cites: { color: "rgba(173,185,204,0.22)", dash: null, arrow: true },
  mentions: { color: "rgba(173,185,204,0.07)", dash: [1, 3], arrow: false },
};

function useWindowSize() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const onResize = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return size;
}

// Convert [[id]] / [[id|label]] wikilinks into clickable anchors, then markdown.
function renderDossier(body, nodesById) {
  const withLinks = body.replace(
    /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
    (_, id, label) => {
      const node = nodesById[id.trim()];
      const text = label || (node ? node.title : id);
      const cls = node ? "wl" : "wl wl-missing";
      return `<a class="${cls}" data-nodeid="${id.trim()}">${text}</a>`;
    }
  );
  return marked.parse(withLinks, { breaks: false });
}

export default function App() {
  const { w, h } = useWindowSize();
  const fgRef = useRef();
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [hoverId, setHoverId] = useState(null);
  const [filters, setFilters] = useState({ claim: true, source: true, site: true, scholar: true });

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}graph.json`)
      .then((r) => r.json())
      .then(setData);
  }, []);

  const nodesById = useMemo(() => {
    const m = {};
    if (data) for (const n of data.nodes) m[n.id] = n;
    return m;
  }, [data]);

  // degree per node → node size
  const degree = useMemo(() => {
    const d = {};
    if (data)
      for (const l of data.links) {
        const s = typeof l.source === "object" ? l.source.id : l.source;
        const t = typeof l.target === "object" ? l.target.id : l.target;
        d[s] = (d[s] || 0) + 1;
        d[t] = (d[t] || 0) + 1;
      }
    return d;
  }, [data]);

  // neighbor sets for hover / selection highlight
  const neighbors = useMemo(() => {
    const map = {};
    if (data) {
      for (const n of data.nodes) map[n.id] = new Set();
      for (const l of data.links) {
        const s = typeof l.source === "object" ? l.source.id : l.source;
        const t = typeof l.target === "object" ? l.target.id : l.target;
        map[s].add(t);
        map[t].add(s);
      }
    }
    return map;
  }, [data]);

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    const nodes = data.nodes.filter((n) => filters[n.type]);
    const keep = new Set(nodes.map((n) => n.id));
    const links = data.links.filter((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      return keep.has(s) && keep.has(t);
    });
    return { nodes, links };
  }, [data, filters]);

  const focusId = hoverId || (selected && selected.id) || null;

  const nodeSize = useCallback((n) => 2.6 + Math.sqrt(degree[n.id] || 1) * 1.25, [degree]);

  const paintNode = useCallback(
    (node, ctx, scale) => {
      const r = nodeSize(node);
      const dim = focusId && focusId !== node.id && !neighbors[focusId]?.has(node.id);
      const color = TYPE_COLOR[node.type] || "#ccc";
      ctx.globalAlpha = dim ? 0.15 : 1;

      // glow for the focused node
      if (focusId === node.id) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
        ctx.fillStyle = color + "33";
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      if (selected && selected.id === node.id) {
        ctx.lineWidth = 1.5 / scale;
        ctx.strokeStyle = "#fff";
        ctx.stroke();
      }

      // label at closer zoom or when focused
      if (scale > 1.3 || focusId === node.id || (selected && selected.id === node.id)) {
        const label = node.title.length > 34 ? node.title.slice(0, 32) + "…" : node.title;
        const fs = Math.max(2.5, 11 / scale);
        ctx.font = `${fs}px 'Space Grotesk', system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = dim ? "rgba(232,230,225,0.25)" : "rgba(232,230,225,0.92)";
        ctx.fillText(label, node.x, node.y + r + 1.5);
      }
      ctx.globalAlpha = 1;
    },
    [focusId, neighbors, nodeSize, selected]
  );

  const paintPointer = useCallback(
    (node, color, ctx) => {
      const r = nodeSize(node) + 2;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fill();
    },
    [nodeSize]
  );

  const linkColor = useCallback(
    (l) => {
      const base = REL_STYLE[l.rel] || REL_STYLE.mentions;
      if (!focusId) return base.color;
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      const on = s === focusId || t === focusId;
      if (on) return base.color;
      return "rgba(120,130,145,0.04)";
    },
    [focusId]
  );

  const dossierRef = useRef(null);
  useEffect(() => {
    const el = dossierRef.current;
    if (!el) return;
    const onClick = (e) => {
      const a = e.target.closest("a.wl");
      if (a && a.dataset.nodeid && nodesById[a.dataset.nodeid]) {
        e.preventDefault();
        const n = nodesById[a.dataset.nodeid];
        setSelected(n);
        if (fgRef.current && n.x != null) fgRef.current.centerAt(n.x, n.y, 600);
      }
    };
    el.addEventListener("click", onClick);
    return () => el.removeEventListener("click", onClick);
  }, [nodesById, selected]);

  useEffect(() => {
    if (data && fgRef.current) {
      const t = setTimeout(() => fgRef.current.zoomToFit(500, 60), 400);
      return () => clearTimeout(t);
    }
  }, [data]);

  if (!data) return <div className="loading">loading the dig…</div>;

  return (
    <div className="app">
      <ForceGraph2D
        ref={fgRef}
        width={w}
        height={h}
        graphData={graphData}
        backgroundColor="#0e1014"
        nodeRelSize={4}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={paintPointer}
        linkColor={linkColor}
        linkWidth={(l) => (l.rel === "disputes" ? 1.4 : l.rel === "supports" ? 1.2 : 0.6)}
        linkLineDash={(l) => (REL_STYLE[l.rel] || {}).dash || null}
        linkDirectionalArrowLength={(l) => ((REL_STYLE[l.rel] || {}).arrow ? 2.6 : 0)}
        linkDirectionalArrowRelPos={0.9}
        linkDirectionalParticles={(l) => (focusId && (l.rel === "supports" || l.rel === "disputes") ? 2 : 0)}
        linkDirectionalParticleWidth={1.6}
        linkDirectionalParticleColor={(l) => (REL_STYLE[l.rel] || REL_STYLE.mentions).color}
        onNodeHover={(n) => setHoverId(n ? n.id : null)}
        onNodeClick={(n) => {
          setSelected(n);
          fgRef.current.centerAt(n.x, n.y, 600);
          fgRef.current.zoom(2.2, 600);
        }}
        onBackgroundClick={() => setSelected(null)}
        cooldownTicks={140}
        d3VelocityDecay={0.28}
        onEngineStop={() => fgRef.current && fgRef.current.zoomToFit(500, 75)}
      />

      <header className="masthead">
        <h1>
          Archeo<span>Logic</span>
        </h1>
        <p>the citation graph — chase the claim to the evidence</p>
      </header>

      <div className="legend">
        <div className="legend-group">
          <span className="lg-title">Nodes</span>
          {Object.keys(TYPE_COLOR).map((t) => (
            <button
              key={t}
              className={`chip ${filters[t] ? "" : "off"}`}
              onClick={() => setFilters((f) => ({ ...f, [t]: !f[t] }))}
            >
              <i style={{ background: TYPE_COLOR[t] }} />
              {TYPE_LABEL[t]}
            </button>
          ))}
        </div>
        <div className="legend-group">
          <span className="lg-title">Edges</span>
          <span className="edge-key"><i className="e-sup" />supports</span>
          <span className="edge-key"><i className="e-dis" />disputes</span>
          <span className="edge-key"><i className="e-cit" />cites</span>
        </div>
      </div>

      <footer className="stats">
        {data.meta.node_count} notes · {data.meta.by_rel.disputes || 0} disputes ·{" "}
        {data.meta.by_rel.supports || 0} supports · {data.meta.by_rel.cites || 0} cites
        <span className="hint"> — click a node to open its dossier</span>
      </footer>

      {selected && (
        <aside className="dossier">
          <button className="close" onClick={() => setSelected(null)}>
            ✕
          </button>
          <div className={`badge badge-${selected.type}`}>{TYPE_LABEL[selected.type]}</div>
          <h2>{selected.title}</h2>
          <div className="meta-row">
            {selected.status && <span className="tag">{selected.status}</span>}
            {selected.type === "claim" || selected.type === "source" ? (
              <span className="conf">
                confidence
                <span className="bar">
                  <span style={{ width: `${Math.round(selected.confidence * 100)}%` }} />
                </span>
                {selected.confidence.toFixed(2)}
              </span>
            ) : null}
          </div>
          <div
            className="body"
            ref={dossierRef}
            dangerouslySetInnerHTML={{ __html: renderDossier(selected.body, nodesById) }}
          />
        </aside>
      )}
    </div>
  );
}
