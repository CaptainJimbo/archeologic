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
const VERDICT_LABEL = {
  contested: "CONTESTED",
  refuted: "REFUTED",
  supported: "SUPPORTED",
  settled: "SETTLED",
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

  // deep-link: /?focus=<node-id> opens that node's dossier (and its funnel)
  useEffect(() => {
    if (!data) return;
    const id = new URLSearchParams(window.location.search).get("focus");
    if (id) {
      const n = data.nodes.find((x) => x.id === id);
      if (n) setSelected(n);
    }
  }, [data]);

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

  // citogenesis funnels: root id -> set of node ids that trace into it (+ root)
  const funnelById = useMemo(() => {
    const m = {};
    if (data)
      for (const n of data.nodes)
        if (n.citogenesis_root)
          m[n.id] = new Set([...(n.funnel_members || []), n.id]);
    return m;
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

  // Focus a citogenesis root → highlight its whole funnel (the shape). Focus any
  // other node → highlight its immediate neighbours.
  const highlightSet = useMemo(() => {
    if (!focusId) return null;
    const s = new Set([focusId]);
    if (neighbors[focusId]) neighbors[focusId].forEach((x) => s.add(x));
    if (funnelById[focusId]) funnelById[focusId].forEach((x) => s.add(x));
    return s;
  }, [focusId, neighbors, funnelById]);

  const openNode = useCallback((n) => {
    if (!n) return;
    setSelected(n);
    if (fgRef.current && n.x != null) fgRef.current.centerAt(n.x, n.y, 600);
  }, []);

  // Step 4: assemble a claim's verdict from the graph edges — the evidence that
  // supports it (tiered primary/echo) and everything that disputes it.
  const verdict = useMemo(() => {
    if (!selected || selected.type !== "claim" || !data) return null;
    const cid = selected.id;
    const evidence = new Map();
    const disputedBy = new Map();
    for (const l of data.links) {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      if (l.rel === "supports" && t === cid && nodesById[s])
        evidence.set(s, nodesById[s]);
      if (l.rel === "cites" && s === cid && nodesById[t] && nodesById[t].type === "source")
        if (!evidence.has(t)) evidence.set(t, nodesById[t]);
      if (l.rel === "disputes") {
        if (t === cid && nodesById[s]) disputedBy.set(s, nodesById[s]);
        if (s === cid && nodesById[t]) disputedBy.set(t, nodesById[t]);
      }
    }
    return { evidence: [...evidence.values()], disputedBy: [...disputedBy.values()] };
  }, [selected, data, nodesById]);

  const nodeSize = useCallback(
    (n) => 2.6 + Math.sqrt(degree[n.id] || 1) * 1.25 + (n.citogenesis_root ? 1.6 : 0),
    [degree]
  );

  const paintNode = useCallback(
    (node, ctx, scale) => {
      const r = nodeSize(node);
      const dim = highlightSet && !highlightSet.has(node.id);
      const color = TYPE_COLOR[node.type] || "#ccc";
      ctx.globalAlpha = dim ? 0.12 : 1;

      // glow for the focused node
      if (focusId === node.id) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
        ctx.fillStyle = color + "33";
        ctx.fill();
      }

      // body — secondary/echo sources drawn hollow (lighter evidentiary weight)
      const echo = node.type === "source" && node.tier === "secondary";
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      if (echo) {
        ctx.fillStyle = "#0e1014";
        ctx.fill();
        ctx.lineWidth = 1.5 / scale;
        ctx.strokeStyle = color;
        ctx.stroke();
      } else {
        ctx.fillStyle = color;
        ctx.fill();
      }

      // citogenesis root — gold ring
      if (node.citogenesis_root) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 2.4, 0, 2 * Math.PI);
        ctx.lineWidth = 1.8 / scale;
        ctx.strokeStyle = "#f5c451";
        ctx.stroke();
      }

      if (selected && selected.id === node.id) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
        ctx.lineWidth = 1.5 / scale;
        ctx.strokeStyle = "#fff";
        ctx.stroke();
      }

      // label when zoomed in, focused, selected, or a citogenesis root
      if (scale > 1.3 || focusId === node.id || node.citogenesis_root ||
          (selected && selected.id === node.id)) {
        const label = node.title.length > 34 ? node.title.slice(0, 32) + "…" : node.title;
        const fs = Math.max(2.5, 11 / scale);
        ctx.font = `${fs}px 'Space Grotesk', system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = dim ? "rgba(232,230,225,0.22)" : "rgba(232,230,225,0.92)";
        ctx.fillText(label, node.x, node.y + r + 1.5);
      }
      ctx.globalAlpha = 1;
    },
    [focusId, highlightSet, nodeSize, selected]
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
      if (!highlightSet) return base.color;
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      return highlightSet.has(s) && highlightSet.has(t)
        ? base.color
        : "rgba(120,130,145,0.04)";
    },
    [highlightSet]
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
        <div className="legend-group">
          <span className="lg-title">Evidence</span>
          <span className="edge-key"><i className="e-root" />citation root</span>
          <span className="edge-key"><i className="e-echo" />echo / review</span>
        </div>
      </div>

      <footer className="stats">
        {data.meta.node_count} notes · {data.meta.by_rel.disputes || 0} disputes ·{" "}
        {data.meta.by_rel.supports || 0} supports · {data.meta.by_rel.cites || 0} cites ·{" "}
        {data.meta.citogenesis_roots ? data.meta.citogenesis_roots.length : 0} citogenesis roots
        <span className="hint"> — click a gold-ringed node to see its funnel</span>
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

          {verdict && (
            <div className="verdict">
              <div className={`verdict-head vh-${selected.status}`}>
                {VERDICT_LABEL[selected.status] || selected.status || "verdict"}
              </div>
              {verdict.evidence.length > 0 && (
                <div className="vsec">
                  <span className="vlabel vfor">Evidence for · {verdict.evidence.length}</span>
                  <ul>
                    {verdict.evidence.map((n) => (
                      <li key={n.id}>
                        <a className="wl" onClick={() => openNode(n)}>{n.title}</a>
                        {n.type === "source" && n.tier && (
                          <span className={`tierpill tp-${n.tier}`}>
                            {n.tier === "secondary" ? "echo" : "primary"}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {verdict.disputedBy.length > 0 && (
                <div className="vsec">
                  <span className="vlabel vagainst">Disputed by · {verdict.disputedBy.length}</span>
                  <ul>
                    {verdict.disputedBy.map((n) => (
                      <li key={n.id}>
                        <a className="wl" onClick={() => openNode(n)}>{n.title}</a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {selected.citogenesis_root && (
            <div className="citogenesis">
              ◈ citation root — <b>{selected.funnel_size}</b> notes funnel into this.
              Everything tracing here is highlighted in the graph.
            </div>
          )}
          {selected.type === "source" && selected.tier && (
            <div className="tierline">
              evidence tier:{" "}
              <b>{selected.tier === "secondary" ? "secondary — echo / review" : "primary"}</b>
            </div>
          )}
          {selected.traces_to && selected.traces_to.length > 0 && (
            <div className="tracesline">
              rests on:{" "}
              {selected.traces_to.map((rid, i) => (
                <span key={rid}>
                  {i > 0 ? ", " : ""}
                  <a
                    className="wl"
                    onClick={() => {
                      const n = nodesById[rid];
                      if (!n) return;
                      setSelected(n);
                      if (fgRef.current && n.x != null) fgRef.current.centerAt(n.x, n.y, 600);
                    }}
                  >
                    {nodesById[rid] ? nodesById[rid].title : rid}
                  </a>
                </span>
              ))}
            </div>
          )}

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
