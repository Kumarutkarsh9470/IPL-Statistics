/**
 * API Configuration for deployment
 * Automatically detects environment (local dev, staging, production)
 */
function getApiEndpoints() {
  const host = window.location.hostname;
  const protocol = window.location.protocol;

  // Local development
  if (host === "localhost" || host === "127.0.0.1") {
    return {
      PHP_API:
        "http://localhost/IPL-statistics-predictions/portal/backend/api/",
      ML_API: "http://localhost:8000/api",
    };
  }

  // Production (Vercel frontend + external backends)
  // Customize these with your actual deployment URLs
  return {
    // PHP Backend on Railway
    PHP_API: "https://ipl-statistics-production.up.railway.app/api",
    // ML API on Vercel
    ML_API: "https://mysql-production-ebe23.up.railway.app/api",
  };
}

const APIS = getApiEndpoints();
const PHP_API_BASE = APIS.PHP_API;
const ML_API_BASE = APIS.ML_API + "/predict";

console.log("📡 API Configuration:", { PHP_API_BASE, ML_API_BASE });

// ============================================================

let allPlayersData = [];
let allTeamsData = [];
let allVenuesData = [];
let sortCol = "total_runs";
let sortDesc = true;
let leaderboardPage = 1;
const LEADERBOARD_PAGE_SIZE = 10;
const MATCHUP_SUGGESTION_LIMIT = 5;
let matchupPlayerNames = [];

// Team Color Scheme
const TEAM_COLORS = {
  "Kolkata Knight Riders": "#9560d4",
  "Chennai Super Kings": "#FFD700",
  "Royal Challengers Bengaluru": "#FF4444",
  "Mumbai Indians": "#ADD8E6",
  "Delhi Capitals": "#1E3A8A",
  "Rajasthan Royals": "#FF69B4",
  "Punjab Kings": "#FFB6C1",
  "Gujarat Titans": "#40E0D0",
  "Lucknow Super Giants": "#4169E1",
  "Sunrisers Hyderabad": "#FF8C00",
};

function getTeamColor(teamName) {
  return TEAM_COLORS[teamName] || "#45f3ff";
}

// Charts
let chartInstanceBatter = null;
let chartInstanceBowler = null;
let chartInstanceToss = null;
let chartInstanceScoreProjection = null;

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initNaturalLanguageQueries();
  initMatchupAutocomplete();

  // Core Data fetches
  fetchTeams().then(() => {
    setupH2HDropdowns();
    // Immediately fetch Team Analytics
    fetchTossData("all");
    fetchFortressHeatmap();
  });
  fetchSeasons();
  fetchVenues();

  // Leaderboard binds
  const seasonFilt = document.getElementById("season-filter");
  const teamFilt = document.getElementById("team-filter");
  if (seasonFilt) seasonFilt.addEventListener("change", fetchLeaderboard);
  if (teamFilt) teamFilt.addEventListener("change", fetchLeaderboard);

  const searchInput = document.getElementById("player-search");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      leaderboardPage = 1;
      renderTable();
    });
  }

  document.querySelectorAll(".premium-table th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const col = th.dataset.sort;
      if (sortCol === col) {
        sortDesc = !sortDesc;
      } else {
        sortCol = col;
        sortDesc = true;
        if (col === "player_name" || col === "economy") sortDesc = false;
      }
      updateSortHeaders(th);
      leaderboardPage = 1;
      renderTable();
    });
  });

  // Matchup Bind
  const matchupBtn = document.getElementById("run-matchup-btn");
  if (matchupBtn) matchupBtn.addEventListener("click", fetchMatchup);

  // Team Analytics Binds
  const tossVenueSel = document.getElementById("toss-venue-select");
  if (tossVenueSel)
    tossVenueSel.addEventListener("change", (e) =>
      fetchTossData(e.target.value),
    );

  const teamPerformanceSel = document.getElementById("team-performance-select");
  if (teamPerformanceSel) {
    teamPerformanceSel.addEventListener("change", (e) =>
      fetchTeamPerformance(e.target.value),
    );
  }

  const venueInsightsSel = document.getElementById("venue-insights-select");
  if (venueInsightsSel) {
    venueInsightsSel.addEventListener("change", (e) =>
      fetchVenueInsights(e.target.value),
    );
  }

  const h2h1 = document.getElementById("h2h-team1");
  const h2h2 = document.getElementById("h2h-team2");
  if (h2h1) h2h1.addEventListener("change", fetchH2H);
  if (h2h2) h2h2.addEventListener("change", fetchH2H);

  // Season Analysis Binds
  const seasonAnalysisSel = document.getElementById("season-analysis-select");
  if (seasonAnalysisSel) {
    seasonAnalysisSel.addEventListener("change", (e) =>
      fetchSeasonAnalysis(e.target.value),
    );
  }

  // Predictive Analytics Binds
  const btnPredMatch = document.getElementById("btn-pred-match");
  if (btnPredMatch) btnPredMatch.addEventListener("click", predictMatch);

  const btnPredScore = document.getElementById("btn-pred-score");
  if (btnPredScore) btnPredScore.addEventListener("click", predictScore);

  const btnPredPlayer = document.getElementById("btn-pred-player");
  if (btnPredPlayer) btnPredPlayer.addEventListener("click", predictPlayer);

  // Over slider live label
  const overSlider = document.getElementById("pred-score-over");
  const overLabel = document.getElementById("pred-score-over-label");
  if (overSlider && overLabel) {
    overSlider.addEventListener("input", () => {
      overLabel.textContent = overSlider.value;
    });
  }

  // Check ML server health
  checkMLServerHealth();
});

async function checkMLServerHealth() {
  const banner = document.getElementById("ml-server-banner");
  if (!banner) return;
  try {
    const res = await fetch(ML_API_BASE + "/health", {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      banner.classList.add("hidden");
    } else {
      banner.classList.remove("hidden");
    }
  } catch {
    banner.classList.remove("hidden");
  }
}

async function predictMatch() {
  const outputEl = document.getElementById("out-pred-match");
  if (!outputEl) return;
  outputEl.classList.remove("hidden");
  outputEl.innerHTML = '<span class="loader">Running ML Inference...</span>';

  const team1Select = document.getElementById("pred-team1");
  const team2Select = document.getElementById("pred-team2");
  const venueSelect = document.getElementById("pred-venue");
  const team1Id = parseInt(team1Select.value);
  const team2Id = parseInt(team2Select.value);
  const venueId = parseInt(venueSelect.value);

  if (!team1Id || !team2Id || !venueId) {
    outputEl.innerHTML =
      '<p style="color:var(--secondary);">Please select all fields.</p>';
    return;
  }

  const tossWinner =
    document.getElementById("pred-toss-winner").value || "team1";
  const tossDecision =
    document.getElementById("pred-toss-decision").value || "bat";
  const matchStage =
    document.getElementById("pred-match-stage")?.value || "league";

  const t1Name = team1Select.options[team1Select.selectedIndex].textContent;
  const t2Name = team2Select.options[team2Select.selectedIndex].textContent;

  try {
    const res = await fetch(ML_API_BASE + "/predict/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team1_id: team1Id,
        team2_id: team2Id,
        venue_id: venueId,
        toss_winner: tossWinner,
        toss_decision: tossDecision,
        match_stage: matchStage,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Prediction failed");

    const p1 = Math.round(data.team1_win_prob * 100);
    const p2 = Math.round(data.team2_win_prob * 100);

    let factorsHtml = "";
    if (data.key_factors && data.key_factors.length > 0) {
      factorsHtml =
        '<div style="display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:1rem;">';
      data.key_factors.forEach((f) => {
        factorsHtml += `<span style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:20px; padding:4px 14px; font-size:0.85rem; color:#ccc;">${f.factor}: <strong>${f.impact}</strong></span>`;
      });
      factorsHtml += "</div>";
    }

    outputEl.innerHTML = `
            <div style="text-align:center;">
                <div style="font-size:0.9rem;color:#888;margin-bottom:0.5rem;">Confidence: <strong style="color:${data.confidence === "high" ? "var(--primary)" : data.confidence === "medium" ? "#f0ad4e" : "#aaa"}">${data.confidence.toUpperCase()}</strong></div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <span style="color:var(--primary); font-weight:800; font-size:1.5rem; text-align:left; flex:1;">${data.team1}</span>
                    <span style="color:#aaa; font-size:1.2rem; margin:0 1rem;">VS</span>
                    <span style="color:var(--secondary); font-weight:800; font-size:1.5rem; text-align:right; flex:1;">${data.team2}</span>
                </div>
                <div class="tug-of-war" style="height:34px; border-radius:17px; margin-bottom:1rem; display:flex; overflow:hidden; background:#222;">
                    <div style="width:${p1}%; background:linear-gradient(90deg, var(--primary), rgba(69,243,255,0.5)); transition:width 1s ease-in-out; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:0.9rem; color:#000;">${p1}%</div>
                    <div style="width:${p2}%; background:linear-gradient(90deg, rgba(255,0,85,0.5), var(--secondary)); transition:width 1s ease-in-out; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:0.9rem; color:#000;">${p2}%</div>
                </div>
                ${factorsHtml}
            </div>
        `;
  } catch (err) {
    outputEl.innerHTML = `<p style="color:var(--secondary); text-align:center;">${escapeHtml(err.message)}</p>`;
    checkMLServerHealth();
  }
}

async function predictScore() {
  const outputEl = document.getElementById("out-pred-score");
  if (!outputEl) return;
  outputEl.classList.remove("hidden");
  outputEl.innerHTML = '<span class="loader">Predicting score...</span>';

  const battingTeamId = parseInt(
    document.getElementById("pred-score-team1").value,
  );
  const bowlingTeamId = parseInt(
    document.getElementById("pred-score-team2").value,
  );
  const venueId = parseInt(document.getElementById("pred-score-venue").value);
  const currentOver = parseInt(
    document.getElementById("pred-score-over")?.value || 10,
  );
  const runsScored = parseInt(
    document.getElementById("pred-score-runs")?.value || 0,
  );
  const wickets = parseInt(
    document.getElementById("pred-score-wickets")?.value || 0,
  );
  const boundaries = parseInt(
    document.getElementById("pred-score-boundaries")?.value || 0,
  );
  const dotBalls = parseInt(
    document.getElementById("pred-score-dots")?.value || 0,
  );
  const extras = parseInt(
    document.getElementById("pred-score-extras")?.value || 0,
  );

  const validationError = validateScoreInputs({
    currentOver,
    runsScored,
    wickets,
    boundaries,
    dotBalls,
    extras,
  });

  if (validationError) {
    outputEl.innerHTML = `<p style="color:var(--secondary); text-align:center;">${escapeHtml(validationError)}</p>`;
    return;
  }

  if (!battingTeamId || !bowlingTeamId || !venueId) {
    outputEl.innerHTML =
      '<p style="color:var(--secondary); text-align:center;">Please select teams and venue.</p>';
    return;
  }

  if (currentOver >= 20) {
    outputEl.innerHTML = `
            <div style="text-align:center;">
                <div style="font-size:0.9rem;color:#888;margin-bottom:0.3rem;">Projected 1st Innings Total</div>
                <div style="font-size:4rem; font-weight:900; color:var(--secondary); text-shadow:0 0 20px rgba(255,0,85,0.4);">
                    ${runsScored}
                </div>
                <div style="font-size:1.2rem; color:#aaa; margin-top:0.3rem;">
                    Range: <strong style="color:#fff;">${runsScored} – ${runsScored}</strong>
                </div>
                <div style="font-size:0.9rem; color:#888; margin-top:0.35rem;">Confidence: <strong style="color:#fff;">100%</strong></div>
                <div style="display:flex; gap:2rem; justify-content:center; margin-top:1rem;">
                    <div><span style="color:var(--primary); font-weight:bold;">${currentOver > 0 ? (runsScored / currentOver).toFixed(1) : 0}</span> <span style="font-size:0.8rem; color:#888;">Current RR</span></div>
                </div>
                <div style="font-size:0.8rem; color:#555; margin-top:0.5rem;">
                    After ${currentOver} overs: ${runsScored}/${wickets}
                </div>
            </div>
        `;
    return;
  }

  try {
    const res = await fetch(ML_API_BASE + "/predict/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        batting_team_id: battingTeamId,
        bowling_team_id: bowlingTeamId,
        venue_id: venueId,
        current_over: currentOver,
        runs_scored: runsScored,
        wickets_fallen: wickets,
        boundaries: boundaries,
        dot_balls: dotBalls,
        extras: extras,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Prediction failed");

    let phaseHtml = "";
    if (data.phase_breakdown) {
      phaseHtml =
        '<div style="display:flex; gap:1.5rem; justify-content:center; margin-top:1rem;">';
      if (data.phase_breakdown.overs_11_15_expected !== undefined) {
        phaseHtml += `<div style="text-align:center;"><div style="font-size:1.5rem; font-weight:bold; color:var(--primary);">${data.phase_breakdown.overs_11_15_expected}</div><div style="font-size:0.8rem; color:#888;">Overs 11-15</div></div>`;
      }
      if (data.phase_breakdown.overs_16_20_expected !== undefined) {
        phaseHtml += `<div style="text-align:center;"><div style="font-size:1.5rem; font-weight:bold; color:var(--secondary);">${data.phase_breakdown.overs_16_20_expected}</div><div style="font-size:0.8rem; color:#888;">Overs 16-20</div></div>`;
      }
      phaseHtml += "</div>";
    }

    outputEl.innerHTML = `
            <div style="text-align:center;">
                <div style="font-size:0.9rem;color:#888;margin-bottom:0.3rem;">Projected 1st Innings Total</div>
                <div style="font-size:4rem; font-weight:900; color:var(--secondary); text-shadow:0 0 20px rgba(255,0,85,0.4);">
                    ${data.predicted_total}
                </div>
                <div style="font-size:1.2rem; color:#aaa; margin-top:0.3rem;">
                    Range: <strong style="color:#fff;">${data.prediction_range[0]} – ${data.prediction_range[1]}</strong>
                </div>
                ${data.confidence !== undefined && data.confidence !== null ? `<div style="font-size:0.9rem; color:#888; margin-top:0.35rem;">Confidence: <strong style="color:#fff;">${data.confidence}%</strong></div>` : ""}
                <div style="display:flex; gap:2rem; justify-content:center; margin-top:1rem;">
                    <div><span style="color:var(--primary); font-weight:bold;">${data.current_run_rate}</span> <span style="font-size:0.8rem; color:#888;">Current RR</span></div>
                    ${data.required_acceleration !== null ? `<div><span style="color:${data.required_acceleration > 0 ? "var(--secondary)" : "var(--primary)"}; font-weight:bold;">${data.required_acceleration > 0 ? "+" : ""}${data.required_acceleration}</span> <span style="font-size:0.8rem; color:#888;">Req. Accel.</span></div>` : ""}
                </div>
                ${phaseHtml}
                <div style="font-size:0.8rem; color:#555; margin-top:0.5rem;">
                    After ${currentOver} overs: ${runsScored}/${wickets}
                </div>
            </div>
        `;
  } catch (err) {
    outputEl.innerHTML = `<p style="color:var(--secondary); text-align:center;">${escapeHtml(err.message)}</p>`;
    checkMLServerHealth();
  }
}

function validateScoreInputs({
  currentOver,
  runsScored,
  wickets,
  boundaries,
  dotBalls,
  extras,
}) {
  const maxRuns = currentOver * 36;
  const totalBalls = currentOver * 6;

  if (runsScored > maxRuns) {
    return `Runs scored cannot be more than ${maxRuns} for ${currentOver} overs.`;
  }

  if (wickets > 10) {
    return "Wickets cannot be more than 10.";
  }

  if (boundaries + dotBalls >= totalBalls) {
    return `Boundaries + dot balls must be less than ${totalBalls} for ${currentOver} overs.`;
  }

  if (runsScored <= 6 * boundaries + extras) {
    return "Runs scored must be greater than 6 * boundaries + extras.";
  }

  return null;
}

async function predictPlayer() {
  const outputEl = document.getElementById("out-pred-player");
  if (!outputEl) return;
  outputEl.classList.remove("hidden");
  outputEl.innerHTML = '<span class="loader">Predicting performance...</span>';

  const playerName = document.getElementById("pred-player-name")?.value?.trim();
  const role = document.getElementById("pred-player-role")?.value || "batting";
  const oppId = parseInt(document.getElementById("pred-player-opp").value);
  const venueId = parseInt(document.getElementById("pred-player-venue").value);

  if (!playerName || !oppId || !venueId) {
    outputEl.innerHTML =
      '<p style="color:var(--secondary); text-align:center;">Please fill in all fields.</p>';
    return;
  }

  try {
    const res = await fetch(ML_API_BASE + "/predict/player", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_name: playerName,
        role: role,
        venue_id: venueId,
        opposition_team_id: oppId,
        match_stage: "league",
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Prediction failed");

    const isBatting = data.role === "batting";
    const mainVal = isBatting ? data.predicted_runs : data.predicted_wickets;
    const mainLabel = isBatting ? "Runs" : "Wickets";
    const mainColor = isBatting ? "var(--primary)" : "var(--secondary)";

    let formHtml = "";
    if (isBatting && data.recent_form) {
      formHtml = `<div style="display:flex; gap:1.5rem; justify-content:center;">
                ${data.recent_form.last_5_avg != null ? `<div><span style="font-weight:bold; color:var(--primary);">${data.recent_form.last_5_avg}</span><div style="font-size:0.75rem; color:#888;">Last 5 Avg</div></div>` : ""}
                ${data.recent_form.last_5_sr != null ? `<div><span style="font-weight:bold; color:var(--primary);">${data.recent_form.last_5_sr}</span><div style="font-size:0.75rem; color:#888;">Last 5 SR</div></div>` : ""}
            </div>`;
    } else if (!isBatting && data.recent_form) {
      formHtml = `<div style="display:flex; gap:1.5rem; justify-content:center;">
                ${data.recent_form.last_5_economy != null ? `<div><span style="font-weight:bold; color:var(--secondary);">${data.recent_form.last_5_economy}</span><div style="font-size:0.75rem; color:#888;">Last 5 Econ</div></div>` : ""}
            </div>`;
    }

    let contextHtml =
      '<div style="display:flex; gap:2rem; justify-content:center; margin-top:1rem; flex-wrap:wrap;">';
    if (data.venue_history && data.venue_history.innings_at_venue > 0) {
      contextHtml += `<div class="stat-box" style="min-width:100px; padding:0.8rem;"><h3 style="color:${mainColor}; margin:0;">${data.venue_history.avg_at_venue ?? "-"}</h3><p style="margin:0; font-size:0.75rem; color:#888;">Avg at Venue (${data.venue_history.innings_at_venue} inn)</p></div>`;
    }
    if (data.vs_opposition && data.vs_opposition.innings_vs > 0) {
      contextHtml += `<div class="stat-box" style="min-width:100px; padding:0.8rem;"><h3 style="color:${mainColor}; margin:0;">${data.vs_opposition.avg_vs ?? "-"}</h3><p style="margin:0; font-size:0.75rem; color:#888;">Avg vs Opp (${data.vs_opposition.innings_vs} inn)</p></div>`;
    }
    contextHtml += "</div>";

    outputEl.innerHTML = `
            <div style="text-align:center;">
                <div style="font-size:0.9rem; color:#888; margin-bottom:0.3rem;">Predicted ${mainLabel} for ${escapeHtml(data.player)}</div>
                <div style="font-size:4rem; font-weight:900; color:${mainColor}; text-shadow:0 0 20px ${mainColor}33;">
                    ${mainVal}
                </div>
                <div style="font-size:1rem; color:#aaa;">Range: <strong style="color:#fff;">${data.prediction_range[0]} – ${data.prediction_range[1]}</strong></div>
                <div style="margin-top:1rem;">${formHtml}</div>
                ${contextHtml}
            </div>
        `;
  } catch (err) {
    outputEl.innerHTML = `<p style="color:var(--secondary); text-align:center;">${escapeHtml(err.message)}</p>`;
    checkMLServerHealth();
  }
}

function initNavigation() {
  const btns = document.querySelectorAll(".nav-btn");
  const sections = document.querySelectorAll(".view-section");

  btns.forEach((btn) => {
    btn.addEventListener("click", () => {
      btns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      sections.forEach((s) => s.classList.add("hidden"));
      const target = document.getElementById(btn.dataset.target + "-section");
      if (target) target.classList.remove("hidden");

      // Lazy load leaderboard data
      if (
        (btn.dataset.target === "players" ||
          btn.dataset.target === "matchup" ||
          btn.dataset.target === "visuals") &&
        allPlayersData.length === 0
      ) {
        fetchLeaderboard().then(() => {
          populateMatchupDropdowns();
          if (btn.dataset.target === "visuals") renderCharts();
        });
      } else if (btn.dataset.target === "visuals") {
        renderCharts();
      }
    });
  });
}

function initNaturalLanguageQueries() {
  bindNaturalLanguageQuery(
    "all",
    "nl-overview-input",
    "nl-overview-btn",
    "nl-overview-output",
    "nl-overview-sql",
  );
  bindNaturalLanguageQuery(
    "all",
    "nl-leaderboard-input",
    "nl-leaderboard-btn",
    "nl-leaderboard-output",
    "nl-leaderboard-sql",
  );
  bindNaturalLanguageQuery(
    "all",
    "nl-h2h-input",
    "nl-h2h-btn",
    "nl-h2h-output",
    "nl-h2h-sql",
  );

  document.querySelectorAll(".nl-example").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      target.value = btn.dataset.query || "";
      target.focus();
    });
  });
}

function bindNaturalLanguageQuery(tab, inputId, buttonId, outputId, sqlId) {
  const input = document.getElementById(inputId);
  const button = document.getElementById(buttonId);
  const output = document.getElementById(outputId);
  const sqlBlock = document.getElementById(sqlId);

  if (!input || !button || !output || !sqlBlock) return;

  button.addEventListener("click", async () => {
    await runNaturalLanguageQuery(tab, input, button, output, sqlBlock);
  });

  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      await runNaturalLanguageQuery(tab, input, button, output, sqlBlock);
    }
  });
}

async function runNaturalLanguageQuery(tab, input, button, output, sqlBlock) {
  const userQuery = (input.value || "").trim();
  if (!userQuery) {
    output.classList.remove("hidden");
    output.innerHTML =
      '<p class="nl-result-error">Please enter a question first.</p>';
    sqlBlock.classList.add("hidden");
    return;
  }

  button.disabled = true;
  button.textContent = "Thinking...";
  output.classList.remove("hidden");
  output.innerHTML =
    '<p class="loader" style="padding:0.4rem 0;">Generating SQL and running query...</p>';
  sqlBlock.classList.add("hidden");

  try {
    const response = await fetch("backend/api/nl_query.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tab, query: userQuery }),
    });

    const responseText = await response.text();
    let json = null;
    try {
      json = JSON.parse(responseText);
    } catch (_) {
      throw new Error(
        "Backend returned an invalid response. Check Apache/PHP logs.",
      );
    }

    if (!response.ok || !json.success) {
      throw new Error(
        json.error || "Failed to process natural language query.",
      );
    }

    sqlBlock.innerHTML = `<details style="margin-bottom:1rem; padding:0.5rem; background:rgba(0,0,0,0.2); border-radius:4px;"><summary style="cursor:pointer; color:#aaa; font-size:0.9rem;">View Generated SQL</summary><pre style="color:var(--secondary); margin-top:0.5rem; white-space:pre-wrap; font-family:monospace;">${escapeHtml(json.sql)}</pre></details>`;
    sqlBlock.classList.remove("hidden");
    renderNaturalLanguageResults(
      output,
      json.chat_response,
      json.columns || [],
      json.rows || [],
    );
  } catch (err) {
    let msg = err.message || "Failed to process natural language query.";
    if (msg.includes("GROQ_API_KEY")) {
      msg =
        "Groq key missing. Add GROQ_API_KEY in project root .env and restart Apache.";
    } else if (/quota exceeded|rate[- ]?limit|billing/i.test(msg)) {
      msg =
        "Groq API credits/quota are exhausted for this key. Update billing or use another Groq key, then retry.";
    }
    output.innerHTML = `<p class="nl-result-error">${escapeHtml(msg)}</p>`;
  } finally {
    button.disabled = false;
    button.textContent = "Run Query";
  }
}

function renderNaturalLanguageResults(
  outputElement,
  chatResponse,
  columns,
  rows,
) {
  outputElement.classList.remove("hidden");

  let contentHtml = "";
  if (chatResponse) {
    contentHtml += `<div class="nl-chat-response" style="background: rgba(69, 243, 255, 0.1); border-left: 4px solid var(--primary); padding: 1rem; margin-bottom: 1rem; border-radius: 4px; line-height:1.5;">
      <strong style="color:var(--primary); font-size: 1.1em;">Analyst AI:</strong> <span style="font-size: 1.05em;">${escapeHtml(chatResponse)}</span>
    </div>`;
  }

  if (!rows || rows.length === 0) {
    outputElement.innerHTML =
      contentHtml +
      '<p class="nl-result-empty">No rows returned for this query.</p>';
    return;
  }

  if (!columns || columns.length === 0) {
    columns = Object.keys(rows[0]);
  }

  let tableHtml =
    '<div class="table-container" style="max-height: 400px; overflow-y: auto;"><table class="premium-table nl-result-table"><thead><tr>';
  columns.forEach((col) => {
    tableHtml += `<th>${escapeHtml(col)}</th>`;
  });
  tableHtml += "</tr></thead><tbody>";

  rows.forEach((row) => {
    tableHtml += "<tr>";
    columns.forEach((col) => {
      const value = row[col] === null || row[col] === undefined ? "" : row[col];
      tableHtml += `<td>${escapeHtml(String(value))}</td>`;
    });
    tableHtml += "</tr>";
  });

  tableHtml += "</tbody></table></div>";
  outputElement.innerHTML = contentHtml + tableHtml;
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ----------------------------------------------------
// 1. DATA FETCHERS
// ----------------------------------------------------
async function fetchTeams() {
  try {
    const response = await fetch("backend/api/teams.php");
    const json = await response.json();
    if (json.success) {
      allTeamsData = json.data;
      const teamDropdown = document.getElementById("team-filter");
      const teamPerformanceSelect = document.getElementById(
        "team-performance-select",
      );

      const predTeam1 = document.getElementById("pred-team1");
      const predTeam2 = document.getElementById("pred-team2");
      const predTossWin = document.getElementById("pred-toss-winner");
      const predScore1 = document.getElementById("pred-score-team1");
      const predScore2 = document.getElementById("pred-score-team2");
      const predOpp = document.getElementById("pred-player-opp");

      const dropdowns = [
        predTeam1,
        predTeam2,
        predScore1,
        predScore2,
        predOpp,
      ].filter(Boolean);

      const shortMaps = {
        "Mumbai Indians": "MI",
        "Chennai Super Kings": "CSK",
        "Royal Challengers Bengaluru": "RCB",
        "Royal Challengers Bangalore": "RCB",
        "Kolkata Knight Riders": "KKR",
        "Sunrisers Hyderabad": "SRH",
        "Rajasthan Royals": "RR",
        "Delhi Capitals": "DC",
        "Delhi Daredevils": "DD",
        "Punjab Kings": "PBKS",
        "Kings XI Punjab": "KXIP",
        "Gujarat Titans": "GT",
        "Lucknow Super Giants": "LSG",
      };

      allTeamsData.forEach((team) => {
        if (teamDropdown) {
          const opt = document.createElement("option");
          opt.value = team.team_id;
          opt.textContent = team.team_name;
          teamDropdown.appendChild(opt);
        }

        if (teamPerformanceSelect) {
          const opt = document.createElement("option");
          opt.value = team.team_id;
          opt.textContent = team.team_name;
          teamPerformanceSelect.appendChild(opt);
        }

        const rawName = team.team_name || "";
        if (!rawName) return; // Skip invalid records

        const sName =
          shortMaps[rawName] ||
          rawName
            .split(" ")
            .map((w) => w[0])
            .join("")
            .toUpperCase();

        dropdowns.forEach((dd) => {
          const opt = document.createElement("option");
          opt.value = team.team_id; // Use team_id for ML API
          opt.textContent = sName;
          dd.appendChild(opt);
        });
      });

      if (teamPerformanceSelect && allTeamsData.length > 0) {
        teamPerformanceSelect.value = allTeamsData[0].team_id;
        fetchTeamPerformance(allTeamsData[0].team_id);
      }
    }
  } catch (e) {
    console.error("Failed to load teams", e);
  }
}

async function fetchSeasons() {
  try {
    const response = await fetch("backend/api/seasons.php");
    const json = await response.json();
    if (json.success) {
      const seasonFilter = document.getElementById("season-filter");
      const seasonAnalysisSel = document.getElementById(
        "season-analysis-select",
      );
      json.data.forEach((season) => {
        if (seasonFilter) {
          const opt = document.createElement("option");
          opt.value = season;
          opt.textContent = season + " Season";
          seasonFilter.appendChild(opt);
        }
        if (seasonAnalysisSel) {
          const opt = document.createElement("option");
          opt.value = season;
          opt.textContent = season + " Season";
          seasonAnalysisSel.appendChild(opt);
        }
      });
    }
  } catch (e) {}
}

async function fetchVenues() {
  try {
    const response = await fetch("backend/api/venues.php");
    const json = await response.json();
    if (json.success && Array.isArray(json.data)) {
      allVenuesData = json.data;
      const vs = document.getElementById("toss-venue-select");
      const venueInsightsSelect = document.getElementById(
        "venue-insights-select",
      );
      const predVenue1 = document.getElementById("pred-venue");
      const predVenue2 = document.getElementById("pred-score-venue");
      const predVenue3 = document.getElementById("pred-player-venue");

      if (vs) vs.innerHTML = '<option value="all">All Venues</option>';
      if (venueInsightsSelect)
        venueInsightsSelect.innerHTML =
          '<option value="">Select Venue</option>';
      if (predVenue1)
        predVenue1.innerHTML = '<option value="">Select Venue</option>';
      if (predVenue2)
        predVenue2.innerHTML = '<option value="">Select Venue</option>';
      if (predVenue3)
        predVenue3.innerHTML = '<option value="">Select Venue</option>';

      const dropdowns = [predVenue1, predVenue2, predVenue3].filter(Boolean);

      json.data.forEach((v) => {
        if (vs) {
          const opt = document.createElement("option");
          opt.value = v.venue_id;
          opt.textContent = v.venue_name;
          vs.appendChild(opt);
        }

        if (venueInsightsSelect) {
          const opt = document.createElement("option");
          opt.value = v.venue_id;
          opt.textContent = v.venue_name;
          venueInsightsSelect.appendChild(opt);
        }

        const rawVenue = v.venue_name || "";
        if (!rawVenue) return;

        const sVenue =
          rawVenue
            .replace(
              /Stadium|Association|Cricket Stadium|Cricket Ground|Ground|International/gi,
              "",
            )
            .trim() || rawVenue;
        dropdowns.forEach((dd) => {
          const opt = document.createElement("option");
          opt.value = v.venue_id; // Use venue_id for ML API
          opt.textContent = sVenue;
          dd.appendChild(opt);
        });
      });

      if (venueInsightsSelect && json.data.length > 0) {
        venueInsightsSelect.value = json.data[0].venue_id;
        fetchVenueInsights(json.data[0].venue_id);
      }
    } else {
      console.error("venues.php returned unexpected payload", json);
    }
  } catch (e) {
    console.error("Failed to load venues", e);
  }
}

async function fetchVenueInsights(venueId) {
  const loader = document.getElementById("venue-insights-loader");
  const content = document.getElementById("venue-insights-content");
  const overallBox = document.getElementById("venue-insights-overall");
  const conditionsBox = document.getElementById("venue-insights-conditions");
  const recentBody = document.getElementById("venue-insights-recent-body");

  if (!loader || !content || !overallBox || !conditionsBox || !recentBody)
    return;
  if (!venueId) {
    content.classList.add("hidden");
    loader.classList.add("hidden");
    return;
  }

  loader.classList.remove("hidden");
  content.classList.add("hidden");

  try {
    const response = await fetch(
      `backend/api/venue_insights.php?venue_id=${venueId}`,
    );
    const json = await response.json();
    if (!response.ok || !json.success) {
      throw new Error(json.error || "Failed to load venue insights.");
    }

    const overview = json.overview || {};
    const homeTeam = json.home_team || {};
    const venue = json.venue || {};
    const conditions = json.conditions || {};

    // Convert outfield speed numeric value to label
    const getOutfieldSpeedLabel = (speed) => {
      if (speed === null || speed === undefined) return "N/A";
      const numSpeed = Number(speed);
      if (numSpeed >= 1.15) return "Fast";
      if (numSpeed >= 0.9) return "Medium";
      return "Slow";
    };

    // Format first innings score - divide by 2 if > 250
    const formatFirstInningsScore = (score) => {
      const numScore = Number(score || 0);
      if (numScore > 250) {
        return (numScore / 2).toFixed(0);
      }
      return numScore.toFixed(0);
    };

    overallBox.innerHTML = `
      <div class="stat-box"><h3 style="word-wrap: break-word; overflow-wrap: break-word; max-width: 100%;">${escapeHtml(venue.venue_name || "-")}</h3><p>Venue</p></div>
      <div class="stat-box"><h3>${escapeHtml(venue.city || "-")}</h3><p>City</p></div>
      <div class="stat-box"><h3>${formatFirstInningsScore(overview.avg_first_innings_score)}</h3><p>Avg 1st Innings Score</p></div>
      <div class="stat-box"><h3>${overview.total_matches || 0}</h3><p>Total Matches</p></div>
      <div class="stat-box"><h3>${escapeHtml(homeTeam.team_name || "N/A")}</h3><p>Home Team</p></div>
      <div class="stat-box"><h3>${homeTeam.wins ?? 0}/${homeTeam.played ?? 0}</h3><p>Home Team Wins at Venue</p></div>
      <div class="stat-box"><h3>${Number(homeTeam.win_pct || 0).toFixed(2)}%</h3><p>Home Team Win Rate</p></div>
    `;

    conditionsBox.innerHTML = `
      <div class="venue-condition-pill"><span class="label">Boundary Distance</span><span class="value">${conditions.boundary_distance_m !== null && conditions.boundary_distance_m !== undefined ? Number(conditions.boundary_distance_m).toFixed(2) + " m" : "N/A"}</span></div>
      <div class="venue-condition-pill"><span class="label">Outfield Speed</span><span class="value">${getOutfieldSpeedLabel(conditions.outfield_speed)}</span></div>
    `;

    recentBody.innerHTML = "";
    (json.recent_matches || []).forEach((m) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(m.match_date || "-")}</td>
        <td>${escapeHtml(m.team1_name || "-")} vs ${escapeHtml(m.team2_name || "-")}</td>
        <td>${escapeHtml(m.winner_name || "No Result")}</td>
        <td>${m.first_innings_score !== null && m.first_innings_score !== undefined ? formatFirstInningsScore(m.first_innings_score) : "-"}</td>
      `;
      recentBody.appendChild(tr);
    });

    if ((json.recent_matches || []).length === 0) {
      recentBody.innerHTML =
        '<tr><td colspan="4" style="text-align:center; color:#aaa;">No recent matches found for this venue.</td></tr>';
    }

    content.classList.remove("hidden");
  } catch (err) {
    overallBox.innerHTML = "";
    conditionsBox.innerHTML = "";
    recentBody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:1rem; color:#ff9aba;">${escapeHtml(err.message)}</td></tr>`;
    content.classList.remove("hidden");
  } finally {
    loader.classList.add("hidden");
  }
}

// ----------------------------------------------------
// 2. TEAM OVERVIEW WIDGETS
// ----------------------------------------------------
async function fetchTossData(venue_id) {
  try {
    const response = await fetch(`backend/api/toss.php?venue_id=${venue_id}`);
    const json = await response.json();
    if (json.success) {
      const data = json.data;
      renderTossChart(data.bat_first_wins, data.chase_wins);
    }
  } catch (e) {
    console.error("Toss Data Err", e);
  }
}

function renderTossChart(batWins, chaseWins) {
  const canvas = document.getElementById("tossChart");
  if (!canvas) return;
  if (chartInstanceToss) chartInstanceToss.destroy();

  const total = batWins + chaseWins;
  if (total === 0) return; // Wait or show empty

  chartInstanceToss = new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: ["Won Batting First", "Won Chasing/Fielding"],
      datasets: [
        {
          data: [batWins, chaseWins],
          backgroundColor: ["rgba(255, 0, 85, 0.8)", "rgba(69, 243, 255, 0.8)"],
          borderColor: ["#ff0055", "#45f3ff"],
          borderWidth: 2,
          hoverOffset: 10,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "70%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#fff", font: { size: 14 } },
        },
      },
    },
  });
}

function setupH2HDropdowns() {
  const h1 = document.getElementById("h2h-team1");
  const h2 = document.getElementById("h2h-team2");
  if (!h1 || !h2) return;

  allTeamsData.forEach((t) => {
    const o1 = document.createElement("option");
    o1.value = t.team_id;
    o1.textContent = t.team_name;
    const o2 = document.createElement("option");
    o2.value = t.team_id;
    o2.textContent = t.team_name;
    h1.appendChild(o1);
    h2.appendChild(o2);
  });

  h1.addEventListener("change", () => updateDropdownColor(h1));
  h2.addEventListener("change", () => updateDropdownColor(h2));
}

function updateDropdownColor(dropdownEl) {
  const selectedTeamName = dropdownEl.options[dropdownEl.selectedIndex].text;
  const teamColor = getTeamColor(selectedTeamName);
  dropdownEl.style.color = teamColor;
  dropdownEl.style.boxShadow = `inset 0 0 8px ${teamColor}40, 0 0 8px ${teamColor}60`;
}

async function fetchH2H() {
  const t1 = document.getElementById("h2h-team1");
  const t2 = document.getElementById("h2h-team2");
  const container = document.getElementById("h2h-result-container");

  if (!t1 || !t2 || t1.value === "" || t2.value === "") return;
  if (t1.value === t2.value) {
    container.classList.add("hidden");
    return;
  }

  try {
    const response = await fetch(
      `backend/api/h2h.php?team_a=${t1.value}&team_b=${t2.value}`,
    );
    const json = await response.json();

    if (json.success) {
      const st = json.data;
      const w1 = st.team_a_wins;
      const w2 = st.team_b_wins;
      const draws = st.no_result;
      const total = st.total_matches;

      const team1Name = t1.options[t1.selectedIndex].text;
      const team2Name = t2.options[t2.selectedIndex].text;
      const team1Color = getTeamColor(team1Name);
      const team2Color = getTeamColor(team2Name);

      const nameEl1 = document.getElementById("h2h-name1");
      const nameEl2 = document.getElementById("h2h-name2");
      const scoreEl1 = document.getElementById("h2h-score1");
      const scoreEl2 = document.getElementById("h2h-score2");

      nameEl1.textContent = team1Name;
      nameEl1.style.color = team1Color;
      nameEl2.textContent = team2Name;
      nameEl2.style.color = team2Color;
      scoreEl1.textContent = w1;
      scoreEl1.style.color = team1Color;
      scoreEl2.textContent = w2;
      scoreEl2.style.color = team2Color;

      document.getElementById("h2h-draws").textContent = draws
        ? `${draws} Draws / No Results`
        : "";

      container.classList.remove("hidden");

      const p1 = total > 0 ? (w1 / total) * 100 : 0;
      const p2 = total > 0 ? (w2 / total) * 100 : 0;
      const pd = total > 0 ? (draws / total) * 100 : 0;

      document.getElementById("tug-bar1").style.width = p1 + "%";
      document.getElementById("tug-bar1").style.backgroundColor =
        `${team1Color}cc`;
      document.getElementById("tug-bar-draw").style.width = pd + "%";
      document.getElementById("tug-bar2").style.width = p2 + "%";
      document.getElementById("tug-bar2").style.backgroundColor =
        `${team2Color}cc`;
    }
  } catch (e) {
    console.error("H2H error", e);
  }
}

async function fetchFortressHeatmap() {
  const container = document.getElementById("heatmap-container");
  const loader = document.getElementById("heatmap-loader");
  if (!container) return;

  try {
    const response = await fetch("backend/api/fortress.php");
    const json = await response.json();
    if (json.success) {
      const data = json.data;

      // Build Matrix Pivot
      let venues = new Set();
      let matrix = {}; // matrix[teamName][venueName] = { played, won, pct }

      data.forEach((r) => {
        venues.add(r.venue_name);
        if (!matrix[r.team_name]) matrix[r.team_name] = {};
        const pct =
          r.matches_played > 0
            ? (r.matches_won / r.matches_played) * 100
            : null;
        matrix[r.team_name][r.venue_name] = pct;
      });

      const venueArray = Array.from(venues).sort();
      const teamArray = Object.keys(matrix).sort();

      let html =
        '<table class="heatmap-table"><thead><tr><th>Team \\ Venue</th>';
      venueArray.forEach((v) => {
        html += `<th>${v.substring(0, 15)}...</th>`;
      });
      html += "</tr></thead><tbody>";

      teamArray.forEach((t) => {
        html += `<tr><td>${t}</td>`;
        venueArray.forEach((v) => {
          const pct = matrix[t][v];
          if (pct !== undefined && pct !== null) {
            let colorStr = getHeatmapColor(pct);
            html += `<td class="heatmap-cell" style="background:${colorStr}" title="${t} at ${v}: ${pct.toFixed(1)}%">${pct.toFixed(0)}%</td>`;
          } else {
            html += `<td style="background:rgba(0,0,0,0.2); color:#555;">-</td>`;
          }
        });
        html += "</tr>";
      });

      html += "</tbody></table>";

      container.innerHTML = html;
      loader.classList.add("hidden");
    }
  } catch (e) {
    console.error(e);
    loader.textContent = "Failed to load heatmap.";
  }
}

function getHeatmapColor(val) {
  if (val >= 50) {
    // Red 69, Green 243, Blue 255 (Cyan)
    let intensity = (val - 50) / 50; // 0 to 1
    return `rgba(69, 243, 255, ${0.2 + intensity * 0.8})`;
  } else {
    // Red 255, Green 0, Blue 85 (Pink/Red)
    let intensity = (50 - val) / 50; // 0 to 1
    return `rgba(255, 0, 85, ${0.2 + intensity * 0.8})`;
  }
}

// ----------------------------------------------------
// 3. LEADERBOARDS AND SCATTERPLOTS (EXISTING)
// ----------------------------------------------------

async function fetchLeaderboard() {
  const loader = document.getElementById("players-loader");
  const tableContainer = document.getElementById("table-container");
  const season = document.getElementById("season-filter").value;
  const team = document.getElementById("team-filter").value;

  if (loader) loader.classList.remove("hidden");
  if (tableContainer) tableContainer.classList.add("hidden");

  try {
    const response = await fetch(
      `backend/api/leaderboard.php?season=${season}&team_id=${team}`,
    );
    const json = await response.json();

    if (json.success) {
      allPlayersData = json.data;
      leaderboardPage = 1;
      allPlayersData.forEach((p) => {
        p.matches = parseInt(p.matches);
        p.total_runs = parseInt(p.total_runs);
        p.average = parseFloat(p.average);
        p.strikeRate = parseFloat(p.strikeRate);
        p.centuries = parseInt(p.centuries);
        p.fifties = parseInt(p.fifties);
        p.fours = parseInt(p.fours);
        p.sixes = parseInt(p.sixes);
        p.wickets = parseInt(p.wickets);
        p.economy = parseFloat(p.economy);
      });

      renderTable();
      populateMatchupDropdowns();

      if (loader) loader.classList.add("hidden");
      if (tableContainer) tableContainer.classList.remove("hidden");

      const visualsBtn = document.querySelector(
        '.nav-btn[data-target="visuals"]',
      );
      if (!visualsBtn || visualsBtn.classList.contains("active")) {
        renderCharts();
      }
    }
  } catch (e) {
    console.error(e);
  }
}

function updateSortHeaders(activeTh) {
  document.querySelectorAll(".premium-table th").forEach((th) => {
    th.classList.remove("active-sort");
    const span = th.querySelector("span");
    if (span) span.remove();
  });

  activeTh.classList.add("active-sort");
  const indicator = document.createElement("span");
  indicator.textContent = sortDesc ? " ▼" : " ▲";
  activeTh.appendChild(indicator);
}

function renderTable() {
  const tbody = document.getElementById("leaderboard-body");
  const pagination = document.getElementById("leaderboard-pagination");
  if (!tbody) return;
  const searchTerm = document
    .getElementById("player-search")
    .value.toLowerCase();

  let filtered = allPlayersData.filter((p) =>
    p.player_name.toLowerCase().includes(searchTerm),
  );

  filtered.sort((a, b) => {
    let valA = a[sortCol];
    let valB = b[sortCol];
    if (typeof valA === "string") {
      return sortDesc ? valB.localeCompare(valA) : valA.localeCompare(valB);
    }
    return sortDesc ? valB - valA : valA - valB;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding: 2rem;">No players found.</td></tr>`;
    if (pagination) {
      pagination.classList.add("hidden");
      pagination.innerHTML = "";
    }
    return;
  }

  const totalItems = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / LEADERBOARD_PAGE_SIZE));
  leaderboardPage = Math.min(Math.max(leaderboardPage, 1), totalPages);
  const startIndex = (leaderboardPage - 1) * LEADERBOARD_PAGE_SIZE;
  const pageData = filtered.slice(
    startIndex,
    startIndex + LEADERBOARD_PAGE_SIZE,
  );

  tbody.innerHTML = "";
  pageData.forEach((p) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
            <td>${p.player_name}</td>
            <td>${p.matches}</td>
            <td style="color:var(--primary)">${p.total_runs}</td>
            <td>${p.average.toFixed(2)}</td>
            <td>${p.strikeRate.toFixed(2)}</td>
            <td>${p.centuries}</td>
            <td>${p.fifties}</td>
            <td>${p.fours}</td>
            <td>${p.sixes}</td>
            <td style="color:var(--secondary); font-weight:bold;">${p.wickets}</td>
            <td>${p.economy.toFixed(2)}</td>
        `;
    tbody.appendChild(tr);
  });

  renderLeaderboardPagination(totalItems, totalPages);
}

function renderLeaderboardPagination(totalItems, totalPages) {
  const pagination = document.getElementById("leaderboard-pagination");
  if (!pagination) return;
  if (totalItems <= LEADERBOARD_PAGE_SIZE) {
    pagination.classList.add("hidden");
    pagination.innerHTML = "";
    return;
  }
  pagination.classList.remove("hidden");
  const fromItem = (leaderboardPage - 1) * LEADERBOARD_PAGE_SIZE + 1;
  const toItem = Math.min(leaderboardPage * LEADERBOARD_PAGE_SIZE, totalItems);
  pagination.innerHTML = `
    <button class="page-btn" id="leaderboard-prev" ${leaderboardPage === 1 ? "disabled" : ""}>Previous</button>
    <span class="page-meta">Showing ${fromItem}-${toItem} of ${totalItems} | Page ${leaderboardPage} of ${totalPages}</span>
    <button class="page-btn" id="leaderboard-next" ${leaderboardPage === totalPages ? "disabled" : ""}>Next</button>
  `;
  const prevBtn = document.getElementById("leaderboard-prev");
  const nextBtn = document.getElementById("leaderboard-next");
  if (prevBtn)
    prevBtn.addEventListener("click", () => {
      if (leaderboardPage > 1) {
        leaderboardPage -= 1;
        renderTable();
      }
    });
  if (nextBtn)
    nextBtn.addEventListener("click", () => {
      if (leaderboardPage < totalPages) {
        leaderboardPage += 1;
        renderTable();
      }
    });
}

function populateMatchupDropdowns() {
  matchupPlayerNames = [
    ...new Set(allPlayersData.map((p) => p.player_name)),
  ].sort((a, b) => a.localeCompare(b));

  // Also populate prediction player datalist
  const predPlayerList = document.getElementById("player-list-pred");
  if (predPlayerList) {
    predPlayerList.innerHTML = "";
    matchupPlayerNames.forEach((name) => {
      const o = document.createElement("option");
      o.value = name;
      predPlayerList.appendChild(o);
    });
  }
}

function initMatchupAutocomplete() {
  const batterInput = document.getElementById("matchup-batter");
  const bowlerInput = document.getElementById("matchup-bowler");
  if (!batterInput || !bowlerInput) return;
  bindMatchupAutocompleteInput(batterInput, "batter-suggestions");
  bindMatchupAutocompleteInput(bowlerInput, "bowler-suggestions");
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".matchup-autocomplete")) {
      hideSuggestions("batter-suggestions");
      hideSuggestions("bowler-suggestions");
    }
  });
}

function bindMatchupAutocompleteInput(inputEl, suggestionId) {
  inputEl.addEventListener("input", () =>
    renderMatchupSuggestions(inputEl, suggestionId),
  );
  inputEl.addEventListener("focus", () =>
    renderMatchupSuggestions(inputEl, suggestionId),
  );
}

function renderMatchupSuggestions(inputEl, suggestionId) {
  const suggestionBox = document.getElementById(suggestionId);
  if (!suggestionBox) return;
  const query = (inputEl.value || "").trim().toLowerCase();
  if (!query || matchupPlayerNames.length === 0) {
    suggestionBox.innerHTML = "";
    suggestionBox.classList.add("hidden");
    return;
  }
  const matches = matchupPlayerNames
    .filter((name) => name.toLowerCase().includes(query))
    .slice(0, MATCHUP_SUGGESTION_LIMIT);
  if (matches.length === 0) {
    suggestionBox.innerHTML = "";
    suggestionBox.classList.add("hidden");
    return;
  }
  suggestionBox.innerHTML = "";
  matches.forEach((name) => {
    const item = document.createElement("div");
    item.className = "matchup-suggestion-item";
    item.textContent = name;
    item.addEventListener("mousedown", (e) => {
      e.preventDefault();
      inputEl.value = name;
      hideSuggestions(suggestionId);
    });
    suggestionBox.appendChild(item);
  });
  suggestionBox.classList.remove("hidden");
}

function hideSuggestions(suggestionId) {
  const suggestionBox = document.getElementById(suggestionId);
  if (!suggestionBox) return;
  suggestionBox.classList.add("hidden");
}

function titleCaseWords(value) {
  return String(value || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) =>
      word
        .split("-")
        .map((part) =>
          part
            ? part.charAt(0).toUpperCase() + part.slice(1).toLowerCase()
            : part,
        )
        .join("-"),
    )
    .join(" ");
}

function formatBattingStyle(style) {
  if (!style) return "Unknown";
  const text = String(style).trim().toLowerCase();
  if (["-", "--", "na", "n/a", "null", "none", "unknown"].includes(text)) {
    return "Unknown";
  }
  return titleCaseWords(style);
}

function formatBowlingStyle(arm, type) {
  const invalidTokens = ["-", "--", "na", "n/a", "null", "none", "unknown"];
  const armTextRaw = arm ? String(arm).trim() : "";
  const typeTextRaw = type ? String(type).trim() : "";
  const armText = invalidTokens.includes(armTextRaw.toLowerCase())
    ? ""
    : armTextRaw;
  const typeText = invalidTokens.includes(typeTextRaw.toLowerCase())
    ? ""
    : typeTextRaw;
  if (!armText && !typeText) return "Unknown";
  const normalizedArm = armText.toLowerCase();
  const normalizedType = typeText.toLowerCase();

  if (armText && typeText) {
    if (
      normalizedArm === normalizedType ||
      normalizedType.includes(normalizedArm) ||
      normalizedArm.includes(normalizedType)
    ) {
      return titleCaseWords(
        armText.length >= typeText.length ? armText : typeText,
      );
    }
    return `${titleCaseWords(armText)} ${titleCaseWords(typeText)}`;
  }

  return titleCaseWords(armText || typeText);
}

async function fetchMatchup() {
  const batterName = document.getElementById("matchup-batter").value;
  const bowlerName = document.getElementById("matchup-bowler").value;

  const batterPlayer = allPlayersData.find((p) => p.player_name === batterName);
  const bowlerPlayer = allPlayersData.find((p) => p.player_name === bowlerName);

  if (!batterPlayer || !bowlerPlayer) {
    alert("Please search and select valid players from the dropdown list.");
    return;
  }

  const batterId = batterPlayer.player_id;
  const bowlerId = bowlerPlayer.player_id;

  const resultDiv = document.getElementById("matchup-result");
  const btn = document.getElementById("run-matchup-btn");
  const batterStyleEl = document.getElementById("mu-batter-style");
  const bowlerStyleEl = document.getElementById("mu-bowler-style");
  btn.textContent = "Calculating...";

  try {
    const response = await fetch(
      `backend/api/matchup.php?batter_id=${batterId}&bowler_id=${bowlerId}`,
    );
    const json = await response.json();

    if (json.success) {
      const st = json.data;
      if (batterStyleEl) {
        batterStyleEl.textContent = formatBattingStyle(
          st.batter_batting_style ?? batterPlayer.batting_style,
        );
      }
      if (bowlerStyleEl) {
        bowlerStyleEl.textContent = formatBowlingStyle(
          st.bowler_bowling_arm ?? bowlerPlayer.bowling_arm,
          st.bowler_bowling_type ?? bowlerPlayer.bowling_type,
        );
      }
      document.getElementById("mu-runs").textContent = st.total_runs;
      document.getElementById("mu-balls").textContent = st.balls_faced;
      document.getElementById("mu-sr").textContent = st.strike_rate.toFixed(2);
      document.getElementById("mu-outs").textContent = st.dismissals;
      document.getElementById("mu-boundaries").textContent =
        st.fours + st.sixes;
      resultDiv.classList.remove("hidden");
    }
  } catch (e) {
    console.error(e);
    alert("Query failed.");
  }
  btn.textContent = "Get Stats";
}

function renderCharts() {
  const canvasBatter = document.getElementById("batterChart");
  const canvasBowler = document.getElementById("bowlerChart");
  if (!canvasBatter || !canvasBowler) return;

  if (chartInstanceBatter) chartInstanceBatter.destroy();
  if (chartInstanceBowler) chartInstanceBowler.destroy();

  const batterData = allPlayersData
    .filter((p) => p.total_runs >= 50)
    .map((p) => ({
      x: p.strikeRate,
      y: p.total_runs,
      name: p.player_name,
    }));

  const bowlerData = allPlayersData
    .filter((p) => p.wickets >= 2)
    .map((p) => ({
      x: p.economy,
      y: p.wickets,
      name: p.player_name,
    }));

  chartInstanceBatter = new Chart(canvasBatter.getContext("2d"), {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Strike Rate vs Runs",
          data: batterData,
          backgroundColor: "rgba(69, 243, 255, 0.6)",
          borderColor: "#45f3ff",
          pointRadius: 5,
          pointHoverRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          callbacks: {
            label: function (ctx) {
              return (
                ctx.raw.name + ": SR " + ctx.parsed.x + ", Runs " + ctx.parsed.y
              );
            },
          },
        },
        legend: { labels: { color: "#fff" } },
      },
      scales: {
        x: {
          title: { display: true, text: "Strike Rate", color: "#fff" },
          ticks: { color: "rgba(255,255,255,0.7)" },
        },
        y: {
          title: { display: true, text: "Total Runs", color: "#fff" },
          ticks: { color: "rgba(255,255,255,0.7)" },
        },
      },
    },
  });

  chartInstanceBowler = new Chart(canvasBowler.getContext("2d"), {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Economy vs Wickets",
          data: bowlerData,
          backgroundColor: "rgba(255, 0, 85, 0.6)",
          borderColor: "#ff0055",
          pointRadius: 5,
          pointHoverRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          callbacks: {
            label: function (ctx) {
              return (
                ctx.raw.name +
                ": Econ " +
                ctx.parsed.x +
                ", Wkts " +
                ctx.parsed.y
              );
            },
          },
        },
        legend: { labels: { color: "#fff" } },
      },
      scales: {
        x: {
          title: { display: true, text: "Economy Rate", color: "#fff" },
          ticks: { color: "rgba(255,255,255,0.7)" },
        },
        y: {
          title: { display: true, text: "Total Wickets", color: "#fff" },
          ticks: { color: "rgba(255,255,255,0.7)" },
        },
      },
    },
  });
}

// ----------------------------------------------------
// 6. TEAM PERFORMANCE
// ----------------------------------------------------
async function fetchTeamPerformance(teamId) {
  const loader = document.getElementById("team-performance-loader");
  const content = document.getElementById("team-performance-content");
  const overallBox = document.getElementById("team-performance-overall");
  const tbody = document.getElementById("team-performance-body");
  if (!loader || !content || !overallBox || !tbody) return;
  if (!teamId) {
    content.classList.add("hidden");
    loader.classList.add("hidden");
    return;
  }
  loader.classList.remove("hidden");
  content.classList.add("hidden");
  try {
    const response = await fetch(
      `backend/api/team_performance.php?team_id=${teamId}`,
    );
    const json = await response.json();
    if (!response.ok || !json.success)
      throw new Error(json.error || "Failed to load team performance.");
    const o = json.overall;
    const teamColor = getTeamColor(json.team.team_name);
    overallBox.innerHTML = `
      <div class="stat-box"><h3>${o.seasons_played}</h3><p>Seasons Played</p></div>
      <div class="stat-box"><h3>${o.total_wins}/${o.total_matches}</h3><p>Total Wins/Matches</p></div>
      <div class="stat-box"><h3 style="color:${teamColor}">${o.overall_win_pct.toFixed(2)}%</h3><p>Overall Win %</p></div>
      <div class="stat-box"><h3>${o.avg_runs_per_match.toFixed(2)}</h3><p>Avg Runs per Match</p></div>
      <div class="stat-box"><h3>${o.best_season || "N/A"}</h3><p>Best Season (${o.best_season_win_pct.toFixed(2)}%)</p></div>
      <div class="stat-box"><h3>${escapeHtml(o.overall_top_scorer.player_name)}</h3><p>Top Scorer (${o.overall_top_scorer.runs} runs)</p></div>
      <div class="stat-box"><h3>${escapeHtml(o.overall_top_wicket_taker.player_name)}</h3><p>Top Wicket-Taker (${o.overall_top_wicket_taker.wickets} wkts)</p></div>
    `;
    tbody.innerHTML = "";
    (json.seasonal || []).forEach((s) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${s.season}</td><td>${s.position ?? "-"}</td><td>${s.played}</td>
        <td style="color:${teamColor}; font-weight:700;">${s.wins}</td><td>${s.losses}</td><td>${s.no_result}</td>
        <td style="color:${teamColor}; font-weight:600;">${s.win_pct.toFixed(2)}%</td>
        <td>${Number(s.avg_runs_per_match).toFixed(2)}</td>
        <td>${escapeHtml(s.top_scorer.player_name)} (${s.top_scorer.runs})</td>
        <td>${escapeHtml(s.top_wicket_taker.player_name)} (${s.top_wicket_taker.wickets})</td>
      `;
      tbody.appendChild(tr);
    });
    content.classList.remove("hidden");
  } catch (err) {
    overallBox.innerHTML = "";
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding:1rem; color:#ff9aba;">${escapeHtml(err.message)}</td></tr>`;
    content.classList.remove("hidden");
  } finally {
    loader.classList.add("hidden");
  }
}

// ----------------------------------------------------
// 7. SEASON ANALYSIS
// ----------------------------------------------------
async function fetchSeasonAnalysis(season) {
  const loader = document.getElementById("season-analysis-loader");
  const content = document.getElementById("season-analysis-content");
  if (!loader || !content || !season) {
    if (content) content.classList.add("hidden");
    if (loader) loader.classList.add("hidden");
    return;
  }
  loader.classList.remove("hidden");
  content.classList.add("hidden");
  try {
    const response = await fetch(
      `backend/api/season_analysis.php?season=${season}`,
    );
    const json = await response.json();
    if (!response.ok || !json.success)
      throw new Error(json.error || "Failed to load season analysis.");
    renderSeasonAnalysis(json);
    content.classList.remove("hidden");
  } catch (err) {
    const tbody = document.getElementById("season-points-table-body");
    if (tbody)
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:1rem; color:#ff9aba;">${escapeHtml(err.message)}</td></tr>`;
    content.classList.remove("hidden");
  } finally {
    loader.classList.add("hidden");
  }
}

function renderSeasonAnalysis(data) {
  const winnerTeam = data.winning_team;
  const runnerUpTeam = data.runner_up_team;
  const winnerColor = getTeamColor(winnerTeam.team_name);
  const runnerUpColor = getTeamColor(runnerUpTeam.team_name);

  const winnerElement = document.getElementById("season-winner-team");
  const runnerUpElement = document.getElementById("season-runner-up-team");
  winnerElement.textContent = winnerTeam.team_name || "-";
  winnerElement.style.color = winnerColor;
  runnerUpElement.textContent = runnerUpTeam.team_name || "-";
  runnerUpElement.style.color = runnerUpColor;

  document.getElementById("season-winner-record").textContent =
    `${winnerTeam.wins}W - ${winnerTeam.losses}L`;
  document.getElementById("season-runner-up-record").textContent =
    `${runnerUpTeam.wins}W - ${runnerUpTeam.losses}L`;
  document.getElementById("season-match-count").textContent =
    data.season_stats.total_matches;

  const battersDiv = document.getElementById("season-top-batters");
  battersDiv.innerHTML = "";
  (data.top_batters || []).forEach((batter, idx) => {
    const div = document.createElement("div");
    div.style.cssText =
      "padding:0.8rem; background:rgba(69,243,255,0.05); border-left:3px solid var(--primary); border-radius:0.5rem;";
    div.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:600;">${idx + 1}. ${escapeHtml(batter.player_name)}</span><span style="color:var(--primary); font-weight:800; font-size:1.1rem;">${batter.total_runs}</span></div><p style="color:rgba(255,255,255,0.6); font-size:0.85rem; margin:0.3rem 0 0 0;">${batter.matches} matches</p>`;
    battersDiv.appendChild(div);
  });

  const bowlersDiv = document.getElementById("season-top-bowlers");
  bowlersDiv.innerHTML = "";
  (data.top_bowlers || []).forEach((bowler, idx) => {
    const div = document.createElement("div");
    div.style.cssText =
      "padding:0.8rem; background:rgba(255,0,85,0.05); border-left:3px solid var(--secondary); border-radius:0.5rem;";
    div.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center;"><span style="font-weight:600;">${idx + 1}. ${escapeHtml(bowler.player_name)}</span><span style="color:var(--secondary); font-weight:800; font-size:1.1rem;">${bowler.wickets}</span></div><p style="color:rgba(255,255,255,0.6); font-size:0.85rem; margin:0.3rem 0 0 0;">${bowler.matches} matches</p>`;
    bowlersDiv.appendChild(div);
  });

  const highest = data.highest_innings;
  const lowest = data.lowest_innings;
  const highestTeamEl = document.getElementById("season-highest-team");
  const lowestTeamEl = document.getElementById("season-lowest-team");
  highestTeamEl.textContent = highest ? highest.team : "-";
  if (highest) highestTeamEl.style.color = getTeamColor(highest.team);
  lowestTeamEl.textContent = lowest ? lowest.team : "-";
  if (lowest) lowestTeamEl.style.color = getTeamColor(lowest.team);
  document.getElementById("season-highest-runs").textContent = highest
    ? highest.runs
    : "-";
  document.getElementById("season-lowest-runs").textContent = lowest
    ? lowest.runs
    : "-";

  const tbody = document.getElementById("season-points-table-body");
  tbody.innerHTML = "";
  (data.points_table || []).forEach((row, idx) => {
    const teamColor = getTeamColor(row.team_name);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight:600; color:${teamColor};">${idx + 1}</td>
      <td style="font-weight:600; color:${teamColor};">${escapeHtml(row.team_name)}</td>
      <td>${row.matches_played}</td>
      <td style="color:${teamColor}; font-weight:700;">${row.wins}</td>
      <td>${row.losses}</td><td>${row.no_result}</td>
      <td style="font-weight:600; color:${teamColor};">${row.win_pct.toFixed(2)}%</td>
      <td style="font-weight:800; color:${teamColor};">${row.points}</td>
    `;
    tbody.appendChild(tr);
  });
}
