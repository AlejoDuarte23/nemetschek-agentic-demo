import base64
import json
from typing import Any


class OptimizationResultsViewer:
    """Self-contained HTML dashboard for cost optimization candidates."""

    def __init__(
        self,
        *,
        summary: dict[str, Any],
        rows: list[dict[str, Any]],
        dimensions: list[str],
        best_candidate_id: str | None = None,
    ) -> None:
        self.summary = summary
        self.rows = rows
        self.dimensions = dimensions
        self.best_candidate_id = best_candidate_id

    def write(self) -> str:
        payload = {
            "summary": self.summary,
            "rows": self.rows,
            "dimensions": self.dimensions,
            "bestCandidateId": self.best_candidate_id,
        }
        encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
        return HTML_TEMPLATE.replace("__OPTIMIZATION_DATA__", encoded)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Optimization Results</title>
  <style>
    :root {
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #64748b;
      --line: #d6dee9;
      --axis: #94a3b8;
      --accent: #0f766e;
      --accent-2: #b45309;
      --bad: #b91c1c;
      --ok: #047857;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }

    .page {
      width: min(1280px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 20px 0 28px;
    }

    header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }

    h1 {
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
      font-weight: 720;
    }

    .subtle {
      margin-top: 5px;
      color: var(--muted);
      font-size: 13px;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }

    .stat {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      min-height: 62px;
    }

    .stat .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }

    .stat .value {
      font-size: 19px;
      line-height: 1.15;
      font-weight: 720;
      overflow-wrap: anywhere;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }

    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }

    .panel-title h2 {
      margin: 0;
      font-size: 15px;
      line-height: 1.2;
    }

    .panel-title span {
      color: var(--muted);
      font-size: 12px;
    }

    .chart-wrap {
      height: 520px;
      padding: 12px;
    }

    svg {
      width: 100%;
      height: 100%;
      display: block;
    }

    .axis line {
      stroke: var(--axis);
      stroke-width: 1;
    }

    .axis-label {
      fill: var(--ink);
      font-size: 11px;
      font-weight: 650;
    }

    .axis-range {
      fill: var(--muted);
      font-size: 10px;
    }

    .polyline {
      fill: none;
      stroke: #2563eb;
      stroke-width: 1.8;
      opacity: 0.42;
    }

    .polyline.best {
      stroke: var(--accent-2);
      stroke-width: 3.2;
      opacity: 0.96;
    }

    .table-wrap {
      width: 100%;
      overflow: auto;
      max-height: 360px;
    }

    table {
      border-collapse: collapse;
      width: 100%;
      min-width: 840px;
      font-size: 12px;
    }

    th,
    td {
      padding: 8px 10px;
      border-bottom: 1px solid #e5e7eb;
      text-align: left;
      white-space: nowrap;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #334155;
      font-weight: 680;
    }

    tr.best-row {
      background: #fffbeb;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      height: 22px;
      padding: 0 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font-size: 11px;
      font-weight: 660;
    }

    .badge.ok {
      color: var(--ok);
      border-color: #a7f3d0;
      background: #ecfdf5;
    }

    .badge.bad {
      color: var(--bad);
      border-color: #fecaca;
      background: #fef2f2;
    }

    .empty {
      display: grid;
      place-items: center;
      min-height: 280px;
      padding: 24px;
      color: var(--muted);
      text-align: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }

    @media (max-width: 900px) {
      .stats {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      header {
        align-items: flex-start;
        flex-direction: column;
      }

      .chart-wrap {
        height: 460px;
      }
    }
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <h1>Optimization Results</h1>
        <div class="subtle" id="studyName"></div>
      </div>
      <div class="subtle" id="updatedAt"></div>
    </header>
    <section class="stats" id="stats"></section>
    <section class="layout" id="content"></section>
  </main>

  <script>
    const encodedPayload = "__OPTIMIZATION_DATA__";
    const payloadBytes = Uint8Array.from(atob(encodedPayload), (char) => char.charCodeAt(0));
    const payload = JSON.parse(new TextDecoder().decode(payloadBytes));
    const rows = payload.rows || [];
    const dims = (payload.dimensions || []).filter((key) =>
      rows.some((row) => Number.isFinite(Number(row[key])))
    );
    const summary = payload.summary || {};
    const bestId = payload.bestCandidateId || summary.best_candidate_id || null;

    const fmt = (value) => {
      if (value === null || value === undefined || value === "") return "-";
      const n = Number(value);
      if (!Number.isFinite(n)) return String(value);
      if (Math.abs(n) >= 1000000) return n.toExponential(2);
      if (Math.abs(n) >= 100) return n.toFixed(1);
      if (Math.abs(n) >= 10) return n.toFixed(2);
      return n.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
    };

    document.getElementById("studyName").textContent = summary.study_name || "Cost optimization study";
    document.getElementById("updatedAt").textContent = summary.objective || "";

    const statItems = [
      ["Candidates", summary.candidate_count ?? rows.length],
      ["Budget", summary.candidate_budget],
      ["Failed", summary.failed_count],
      ["Infeasible", summary.infeasible_count],
      ["Best cost", summary.best_objective_value],
    ];
    document.getElementById("stats").innerHTML = statItems.map(([label, value]) => `
      <div class="stat">
        <div class="label">${label}</div>
        <div class="value">${fmt(value)}</div>
      </div>
    `).join("");

    const content = document.getElementById("content");
    if (!rows.length || !dims.length) {
      content.innerHTML = `<div class="empty">No recorded optimization candidates are available yet.</div>`;
    } else {
      content.innerHTML = `
        <section class="panel">
          <div class="panel-title">
            <h2>Parallel Coordinates</h2>
            <span>${rows.length} candidates, ${dims.length} numeric dimensions</span>
          </div>
          <div class="chart-wrap"><svg id="parallel"></svg></div>
        </section>
        <section class="panel">
          <div class="panel-title">
            <h2>Candidate Runs</h2>
            <span>Best candidate is highlighted</span>
          </div>
          <div class="table-wrap" id="tableWrap"></div>
        </section>
      `;
      drawParallelCoordinates();
      drawTable();
    }

    function niceLabel(key) {
      return key
        .replace(/step_geo\.sec_/g, "")
        .replace(/step_geo_tech\.sec_/g, "")
        .replace(/_/g, " ")
        .replace(/\./g, " / ");
    }

    function drawParallelCoordinates() {
      const svg = document.getElementById("parallel");
      const box = svg.getBoundingClientRect();
      const width = Math.max(720, box.width || 1000);
      const height = Math.max(420, box.height || 500);
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.innerHTML = "";

      const margin = { top: 36, right: 34, bottom: 72, left: 42 };
      const plotW = width - margin.left - margin.right;
      const plotH = height - margin.top - margin.bottom;
      const axisGap = dims.length > 1 ? plotW / (dims.length - 1) : plotW;

      const ranges = Object.fromEntries(dims.map((dim) => {
        const values = rows.map((row) => Number(row[dim])).filter(Number.isFinite);
        let min = Math.min(...values);
        let max = Math.max(...values);
        if (min === max) {
          min -= 1;
          max += 1;
        }
        return [dim, { min, max }];
      }));

      const y = (dim, value) => {
        const n = Number(value);
        const range = ranges[dim];
        const t = Number.isFinite(n) ? (n - range.min) / (range.max - range.min) : 0.5;
        return margin.top + plotH - (t * plotH);
      };

      const x = (index) => margin.left + index * axisGap;
      const ns = "http://www.w3.org/2000/svg";

      rows.forEach((row) => {
        const points = dims.map((dim, index) => `${x(index)},${y(dim, row[dim])}`).join(" ");
        const poly = document.createElementNS(ns, "polyline");
        poly.setAttribute("points", points);
        poly.setAttribute("class", row.candidate_id === bestId ? "polyline best" : "polyline");
        svg.appendChild(poly);
      });

      dims.forEach((dim, index) => {
        const gx = x(index);
        const group = document.createElementNS(ns, "g");
        group.setAttribute("class", "axis");

        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", gx);
        line.setAttribute("x2", gx);
        line.setAttribute("y1", margin.top);
        line.setAttribute("y2", margin.top + plotH);
        group.appendChild(line);

        const maxLabel = document.createElementNS(ns, "text");
        maxLabel.setAttribute("x", gx);
        maxLabel.setAttribute("y", margin.top - 8);
        maxLabel.setAttribute("text-anchor", "middle");
        maxLabel.setAttribute("class", "axis-range");
        maxLabel.textContent = fmt(ranges[dim].max);
        group.appendChild(maxLabel);

        const minLabel = document.createElementNS(ns, "text");
        minLabel.setAttribute("x", gx);
        minLabel.setAttribute("y", margin.top + plotH + 16);
        minLabel.setAttribute("text-anchor", "middle");
        minLabel.setAttribute("class", "axis-range");
        minLabel.textContent = fmt(ranges[dim].min);
        group.appendChild(minLabel);

        const label = document.createElementNS(ns, "text");
        label.setAttribute("x", gx);
        label.setAttribute("y", margin.top + plotH + 36);
        label.setAttribute("text-anchor", "end");
        label.setAttribute("class", "axis-label");
        label.setAttribute("transform", `rotate(-32 ${gx} ${margin.top + plotH + 36})`);
        label.textContent = niceLabel(dim);
        group.appendChild(label);

        svg.appendChild(group);
      });
    }

    function drawTable() {
      const keys = ["candidate_id", "status", "feasible", "objective_value", ...dims];
      const header = keys.map((key) => `<th>${niceLabel(key)}</th>`).join("");
      const body = rows.map((row) => {
        const bestClass = row.candidate_id === bestId ? "best-row" : "";
        const cells = keys.map((key) => {
          if (key === "feasible") {
            const ok = Boolean(row[key]);
            return `<td><span class="badge ${ok ? "ok" : "bad"}">${ok ? "yes" : "no"}</span></td>`;
          }
          return `<td>${fmt(row[key])}</td>`;
        }).join("");
        return `<tr class="${bestClass}">${cells}</tr>`;
      }).join("");
      document.getElementById("tableWrap").innerHTML = `<table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
    }
  </script>
</body>
</html>
"""
