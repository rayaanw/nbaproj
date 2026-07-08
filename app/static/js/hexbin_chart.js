/**
 * T-033.2: reusable shot chart helper, built on Plotly.js.
 *
 * Renders NBA shot data (court x/y coordinates + xFG%/make flag) against an
 * actual basketball court diagram, so shot locations read as real points on
 * a court rather than an abstract grid. A light density layer gives the
 * classic NBA.com "hot zone" heatmap feel; individual shots are drawn as
 * make/miss-colored dots at their exact court location, with hover
 * tooltips. Used by the Shot Explorer (T-036) and Player Page (T-040).
 *
 * Coordinate system matches nba_api's shotchartdetail LOC_X/LOC_Y directly:
 * tenths of a foot, hoop at (0, 0), baseline around y=-47.5, half-court
 * around y=422.5, sideline-to-sideline x in [-250, 250] (the NBA court is
 * 50ft wide). Court dimensions below are the standard constants used across
 * most public NBA shot-chart tooling (e.g. the widely-replicated
 * matplotlib `draw_court()` recipe), converted to the same units.
 */

const COURT_LINE_COLOR = "rgba(255, 255, 255, 0.9)";

/** Points along a circular arc, in standard math convention (0 deg = +x axis,
 * counterclockwise), for court features that aren't straight lines.
 */
function arcPoints(cx, cy, radius, startDeg, endDeg, steps = 48) {
  const xs = [];
  const ys = [];
  for (let i = 0; i <= steps; i++) {
    const deg = startDeg + ((endDeg - startDeg) * i) / steps;
    const rad = (deg * Math.PI) / 180;
    xs.push(cx + radius * Math.cos(rad));
    ys.push(cy + radius * Math.sin(rad));
  }
  return { xs, ys };
}

function courtLineTrace(xs, ys, lineOverrides = {}) {
  return {
    x: xs,
    y: ys,
    mode: "lines",
    type: "scatter",
    line: Object.assign({ color: COURT_LINE_COLOR, width: 2 }, lineOverrides),
    hoverinfo: "skip",
    showlegend: false,
  };
}

function arcTrace(cx, cy, radius, startDeg, endDeg, lineOverrides = {}) {
  const { xs, ys } = arcPoints(cx, cy, radius, startDeg, endDeg);
  return courtLineTrace(xs, ys, lineOverrides);
}

function segmentTrace(x0, y0, x1, y1, lineOverrides = {}) {
  return courtLineTrace([x0, x1], [y0, y1], lineOverrides);
}

function rectTrace(x0, y0, x1, y1, lineOverrides = {}) {
  return courtLineTrace([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], lineOverrides);
}

/** Builds the full set of court-diagram traces (boundary, paint, hoop,
 * backboard, free-throw circle, restricted area, three-point line).
 */
function getCourtTraces() {
  return [
    rectTrace(-250, -47.5, 250, 422.5), // court boundary
    rectTrace(-80, -47.5, 80, 142.5), // paint (outer box)
    rectTrace(-60, -47.5, 60, 142.5), // free-throw lane (inner box)
    arcTrace(0, 0, 7.5, 0, 360), // hoop
    segmentTrace(-30, -7.5, 30, -7.5, { width: 2 }), // backboard
    arcTrace(0, 142.5, 60, 0, 180), // free-throw circle, far half (solid)
    arcTrace(0, 142.5, 60, 180, 360, { dash: "dash" }), // free-throw circle, near half (dashed)
    arcTrace(0, 0, 40, 0, 180), // restricted-area arc
    segmentTrace(-220, -47.5, -220, 92.5), // left corner-three line
    segmentTrace(220, -47.5, 220, 92.5), // right corner-three line
    arcTrace(0, 0, 237.5, 22, 158), // three-point arc
  ];
}

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

  // Light density layer for the classic "hot zone" heatmap feel — kept
  // subtle (low opacity, dark colorscale floor) so it reads as a background
  // heat glow rather than obscuring the court diagram or individual shots.
  const densityTrace = {
    x: xValues,
    y: yValues,
    type: "histogram2d",
    colorscale: [
      [0, "rgba(22,27,34,0)"],
      [0.5, "rgba(255,107,53,0.45)"],
      [1, "rgba(255,209,102,0.65)"],
    ],
    nbinsx: 25,
    nbinsy: 25,
    showscale: false,
    hoverinfo: "skip",
  };

  // Individual shots, colored by outcome and placed at their real court
  // location — this is the direct answer to "where was each shot taken":
  // every dot's (x, y) is that shot's actual LOC_X/LOC_Y on the court.
  const madeTrace = buildShotScatter(shots, xValues, yValues, true);
  const missedTrace = buildShotScatter(shots, xValues, yValues, false);

  const courtTraces = getCourtTraces();

  const layout = {
    title: options.title || "Shot Chart",
    paper_bgcolor: "#0e1117",
    plot_bgcolor: "#0e1117",
    font: { color: "#e6edf3" },
    xaxis: { visible: false, range: [-260, 260] },
    // scaleanchor locks the y-axis to the x-axis at a 1:1 ratio so the
    // hoop/arcs render as actual circles instead of stretched ellipses.
    yaxis: { visible: false, range: [-60, 432.5], scaleanchor: "x", scaleratio: 1 },
    margin: { t: 40, l: 10, r: 10, b: 10 },
    height: 580,
    showlegend: true,
    legend: { orientation: "h", y: -0.02, font: { size: 11 } },
  };

  Plotly.newPlot(
    containerId,
    [densityTrace, ...courtTraces, missedTrace, madeTrace],
    layout,
    { displayModeBar: false, responsive: true }
  );
}

function buildShotScatter(shots, xValues, yValues, made) {
  const indices = shots.map((_, i) => i).filter((i) => !!shots[i].shot_made_flag === made);
  return {
    x: indices.map((i) => xValues[i]),
    y: indices.map((i) => yValues[i]),
    mode: "markers",
    type: "scatter",
    name: made ? "Made" : "Missed",
    marker: {
      size: 6,
      color: made ? "#3fb950" : "#f85149",
      line: { color: "#0e1117", width: 0.5 },
      opacity: 0.85,
    },
    text: indices.map((i) => {
      const s = shots[i];
      return (
        `${s.action_type || "Shot"}<br>` +
        `Distance: ${s.shot_distance != null ? s.shot_distance.toFixed(1) : "?"} ft<br>` +
        `xFG%: ${s.xfg_pct != null ? (s.xfg_pct * 100).toFixed(1) + "%" : "?"}<br>` +
        `Result: ${made ? "Made" : "Missed"}`
      );
    }),
    hoverinfo: "text",
  };
}
