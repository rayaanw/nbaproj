/**
 * T-033.2: reusable hexbin/heatmap shot chart helper, built on Plotly.js.
 *
 * Renders NBA shot data (court x/y coordinates + xFG%/make flag) as a
 * hexagonal-binned density plot with hover tooltips, in the classic
 * NBA.com shot-chart style. Used by the Shot Explorer (T-036) and Player
 * Page (T-040).
 */

/**
 * @param {string} containerId - DOM id of the target <div> to render into.
 * @param {Array<Object>} shots - array of shot objects, each with at least:
 *   { loc_x, loc_y, shot_distance, action_type, xfg_pct, shot_made_flag }
 * @param {Object} [options]
 * @param {string} [options.title] - chart title.
 */
function renderHexbinChart(containerId, shots, options = {}) {
  const container = document.getElementById(containerId);
  if (!container) {
    console.error(`renderHexbinChart: no element with id "${containerId}"`);
    return;
  }

  if (!shots || shots.length === 0) {
    container.innerHTML = '<p class="stat-label">No shots match the current filters.</p>';
    return;
  }

  const xValues = shots.map((s) => s.loc_x);
  const yValues = shots.map((s) => s.loc_y);

  // Hexbin density layer — this is what gives the classic NBA.com "heatmap"
  // look. Plotly's `histogram2dcontour`-adjacent hexbin support isn't a
  // built-in trace type, so we approximate it with a 2D histogram
  // (equivalent visual effect: binned shot density across the court).
  const densityTrace = {
    x: xValues,
    y: yValues,
    type: "histogram2d",
    colorscale: [
      [0, "#161b22"],
      [0.5, "#ff6b35"],
      [1, "#ffd166"],
    ],
    nbinsx: 25,
    nbinsy: 25,
    showscale: false,
    opacity: 0.85,
    hoverinfo: "skip",
  };

  // Scatter overlay carrying the actual per-shot tooltip data (T-036.3).
  const scatterTrace = {
    x: xValues,
    y: yValues,
    mode: "markers",
    type: "scatter",
    marker: { size: 4, color: "rgba(255,255,255,0.35)" },
    text: shots.map(
      (s) =>
        `${s.action_type || "Shot"}<br>` +
        `Distance: ${s.shot_distance != null ? s.shot_distance.toFixed(1) : "?"} ft<br>` +
        `xFG%: ${s.xfg_pct != null ? (s.xfg_pct * 100).toFixed(1) + "%" : "?"}<br>` +
        `Result: ${s.shot_made_flag ? "Made" : "Missed"}`
    ),
    hoverinfo: "text",
  };

  const layout = {
    title: options.title || "Shot Chart",
    paper_bgcolor: "#0e1117",
    plot_bgcolor: "#0e1117",
    font: { color: "#e6edf3" },
    xaxis: { visible: false, range: [-250, 250] },
    yaxis: { visible: false, range: [-50, 420] },
    margin: { t: 40, l: 10, r: 10, b: 10 },
    height: 500,
  };

  Plotly.newPlot(containerId, [densityTrace, scatterTrace], layout, {
    displayModeBar: false,
    responsive: true,
  });
}
