import base64
import json
from typing import Any


class PlotlyFigureViewer:
    """Self-contained HTML renderer for a Plotly figure JSON payload."""

    def __init__(self, *, figure: str | dict[str, Any], title: str) -> None:
        self.figure = figure
        self.title = title

    def write(self) -> str:
        figure_json = self.figure if isinstance(self.figure, str) else json.dumps(self.figure)
        payload = {
            "title": self.title,
            "figure": figure_json,
        }
        encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
        return HTML_TEMPLATE.replace("__PLOTLY_FIGURE_DATA__", encoded)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Plotly Figure</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    :root {
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #64748b;
      --line: #d6dee9;
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
      width: min(1440px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 18px 0 24px;
    }

    header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 12px;
    }

    h1 {
      margin: 0;
      font-size: 21px;
      line-height: 1.2;
      font-weight: 720;
    }

    .meta {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }

    #plot {
      min-height: 760px;
      height: calc(100vh - 90px);
      width: 100%;
    }

    .message {
      display: grid;
      place-items: center;
      min-height: 420px;
      color: var(--muted);
      padding: 24px;
      text-align: center;
    }
  </style>
</head>
<body>
  <main class="page">
    <header>
      <h1 id="title">Plotly Figure</h1>
      <div class="meta" id="meta"></div>
    </header>
    <section class="panel">
      <div id="plot"></div>
    </section>
  </main>
  <script>
    const encoded = "__PLOTLY_FIGURE_DATA__";
    const payload = JSON.parse(atob(encoded));
    const plot = document.getElementById("plot");
    const title = document.getElementById("title");
    const meta = document.getElementById("meta");

    title.textContent = payload.title || "Plotly Figure";

    function dtypeArray(dtype, binary) {
      const raw = atob(binary);
      const buffer = new ArrayBuffer(raw.length);
      const bytes = new Uint8Array(buffer);
      for (let i = 0; i < raw.length; i += 1) {
        bytes[i] = raw.charCodeAt(i);
      }
      switch (dtype) {
        case "f8": return Array.from(new Float64Array(buffer));
        case "f4": return Array.from(new Float32Array(buffer));
        case "i4": return Array.from(new Int32Array(buffer));
        case "u4": return Array.from(new Uint32Array(buffer));
        case "i2": return Array.from(new Int16Array(buffer));
        case "u2": return Array.from(new Uint16Array(buffer));
        case "i1": return Array.from(new Int8Array(buffer));
        case "u1": return Array.from(new Uint8Array(buffer));
        default: return null;
      }
    }

    function reshape(values, shapeText) {
      if (!shapeText || typeof shapeText !== "string") {
        return values;
      }
      const shape = shapeText.split(",").map((item) => Number(item.trim())).filter(Number.isFinite);
      if (shape.length !== 2) {
        return values;
      }
      const [rows, cols] = shape;
      const matrix = [];
      for (let row = 0; row < rows; row += 1) {
        matrix.push(values.slice(row * cols, (row + 1) * cols));
      }
      return matrix;
    }

    function decodeTypedArrays(value) {
      if (Array.isArray(value)) {
        return value.map(decodeTypedArrays);
      }
      if (!value || typeof value !== "object") {
        return value;
      }
      if (typeof value.bdata === "string" && typeof value.dtype === "string") {
        const decoded = dtypeArray(value.dtype, value.bdata);
        if (decoded) {
          return reshape(decoded, value.shape);
        }
      }
      return Object.fromEntries(
        Object.entries(value).map(([key, child]) => [key, decodeTypedArrays(child)])
      );
    }

    function showMessage(message) {
      plot.innerHTML = `<div class="message">${message}</div>`;
    }

    try {
      const figure = decodeTypedArrays(JSON.parse(payload.figure));
      const data = figure.data || [];
      const layout = {
        ...(figure.layout || {}),
        autosize: true,
      };
      const config = {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
      };
      meta.textContent = `${data.length} traces`;
      Plotly.newPlot(plot, data, layout, config);
      window.addEventListener("resize", () => Plotly.Plots.resize(plot));
    } catch (error) {
      console.error(error);
      showMessage("Could not render the Plotly figure.");
    }
  </script>
</body>
</html>
"""
