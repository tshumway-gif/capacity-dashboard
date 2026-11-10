#!/usr/bin/env python3
"""
REG FINS GTM Team Capacity Dashboard
Usage: pip install flask && python server.py
Open:  http://localhost:8080

Data is served from data.json in this directory.
To refresh: ask Claude Code to "update dashboard data", then click Refresh.
"""

import json
import os
import sys
from datetime import datetime

try:
    from flask import Flask, jsonify, render_template_string
except ImportError:
    print("Flask not found. Install it: pip install flask")
    sys.exit(1)

app = Flask(__name__)

# ── Configuration ───────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
KNOWN_PERSON_IDS = {
    # Tom Shumway's team
    '0053y00000G0dOfAAJ', '0053y00000GhmHMAAZ', '0053y00000GekI9AAJ',
    '00530000009NOv6AAG', '0053y00000FUv9aAAD', '00530000009MZ2eAAG',
    '0053y00000GEodCAAT', '0053y00000GoyRXAAZ', '0053y00000FUnViAAL',
    '0053y00000GZZlRAAX',
    # Anita Chow's team
    '0053y00000GBiiOAAT', '00530000007QtfcAAC', '0050M00000C1TERQA3',
    '00530000007Pw2HAAS', '0053y00000Gshp1AAB', '0053y00000G8xAZAAZ',
    '005ed000002EIFFAA4', '0050M00000ATZYOQA5', '0053y00000Bz6JVAAZ',
    '0053y00000FyYJEAA3',
}

# ── Refresh config ───────────────────────────────────────────────
_BASE        = os.path.dirname(os.path.abspath(__file__))
_PENDING_FLAG = os.path.join(_BASE, 'pending_refresh.flag')


# ── Data file access ────────────────────────────────────────────
_file_mtime = 0
_cached_data = None


def get_data(force=False):
    global _file_mtime, _cached_data
    try:
        mtime = os.path.getmtime(DATA_FILE)
    except FileNotFoundError:
        raise RuntimeError(f"data.json not found at {DATA_FILE}. Ask Claude Code to refresh the dashboard data.")
    if force or mtime != _file_mtime or _cached_data is None:
        with open(DATA_FILE, encoding='utf-8') as f:
            _cached_data = json.load(f)
        _file_mtime = mtime
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded data.json (refreshed: {_cached_data.get('lastRefreshed','')})")
    return _cached_data


def get_person_dsrs(person_id):
    data = get_data()
    return data.get('personDSRs', {}).get(person_id, [])


# ── API routes ──────────────────────────────────────────────────
@app.route('/api/data')
def api_data():
    return jsonify(get_data())


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    # Write a flag file so Claude Code knows a refresh was requested
    try:
        with open(_PENDING_FLAG, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass
    # Re-read data.json from disk (picks up any refresh Claude Code already did)
    try:
        data = get_data(force=True)
        return jsonify({'ok': True, 'lastRefreshed': data['lastRefreshed'],
                        'seeded': data.get('seeded', False)})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


@app.route('/api/person/<person_id>/dsrs')
def api_person_dsrs(person_id):
    # Validate person_id against known whitelist to prevent injection
    if person_id not in KNOWN_PERSON_IDS:
        return jsonify({'error': 'Unknown person'}), 404
    try:
        dsrs = get_person_dsrs(person_id)
        return jsonify({'dsrs': dsrs})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@app.route('/')
def index():
    return render_template_string(HTML)


# ── Dashboard HTML ──────────────────────────────────────────────
# All Salesforce data is inserted via textContent (not innerHTML) in JS
# to prevent XSS. Only static strings use innerHTML for structure.
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>REG FINS GTM &mdash; Team Capacity</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0F1823;color:#D8E4F0;min-height:100vh}

/* header */
header{background:#0057A8;color:#fff;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 10px rgba(0,0,0,.5)}
header h1{font-size:1.1rem;font-weight:600}
header .subtitle{font-size:.75rem;opacity:.75;margin-top:2px}
.refresh-btn{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.3);color:#fff;padding:7px 14px;border-radius:6px;font-size:.82rem;cursor:pointer;transition:background .15s}
.refresh-btn:hover{background:rgba(255,255,255,.22)}
.refresh-btn:disabled{opacity:.5;cursor:not-allowed}
.refresh-btn svg{width:14px;height:14px;flex-shrink:0}
.refresh-btn.loading svg{animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.last-updated{font-size:.7rem;opacity:.65;margin-top:3px;text-align:right}
.seeded-pill{font-size:.65rem;background:#FE9339;color:#fff;padding:2px 6px;border-radius:4px;margin-left:6px}

/* layout */
main{max-width:1280px;margin:0 auto;padding:20px 24px}

/* KPI strip */
.kpi-strip{display:grid;grid-template-columns:repeat(7,1fr);gap:14px;margin-bottom:24px}
.kpi-card{background:#182434;border-radius:10px;padding:18px 20px;box-shadow:0 2px 8px rgba(0,0,0,.35);border:1px solid #243648}
.kpi-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:#6E8FAD;margin-bottom:6px}
.kpi-card-booked{background:#0A1F14;border-color:#1E4030}
.kpi-card-booked .kpi-label{color:#5BA887}
.kpi-card-booked .kpi-value{color:#3FBA7F}
.kpi-value{font-size:1.65rem;font-weight:700;line-height:1;color:#EBF3FF}
.kpi-sub{font-size:.72rem;color:#6E8FAD;margin-top:5px}

/* member filter */
.member-filter-card{background:#182434;border:1px solid #243648;border-radius:10px;padding:14px 20px;margin-bottom:24px}
.member-filter-header{font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:#6E8FAD;margin-bottom:10px}
.member-filter-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px 16px}
@media(max-width:900px){.member-filter-grid{grid-template-columns:repeat(3,1fr)}}
.member-filter-item{display:flex;align-items:center;gap:7px}
.member-filter-item input[type=checkbox]{accent-color:#1589EE;width:14px;height:14px;cursor:pointer;flex-shrink:0}
.member-filter-item label{font-size:.8rem;color:#D8E4F0;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.member-filter-group{grid-column:1/-1;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#4BA8E8;padding-top:8px;border-top:1px solid #243648;margin-top:2px}
.member-filter-group:first-child{border-top:none;padding-top:0;margin-top:0}

/* section heading */
.section-heading{font-size:.8rem;text-transform:uppercase;letter-spacing:.07em;color:#6E8FAD;margin-bottom:12px;margin-top:4px}

/* charts */
.forecast-row{display:grid;grid-template-columns:2fr 1fr;gap:20px;margin-bottom:24px}
@media(max-width:900px){.forecast-row{grid-template-columns:1fr}}
.forecast-card{background:#182434;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.35);border:1px solid #243648}
.forecast-card h2{font-size:.85rem;font-weight:600;color:#B8CEEA;margin-bottom:16px}
.nextup-card{background:#182434;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.35);border:1px solid #243648}
.nextup-card h2{font-size:.85rem;font-weight:600;color:#B8CEEA;margin-bottom:4px}
.nextup-subtitle{font-size:.68rem;color:#6E8FAD;margin-bottom:14px}
.nextup-row{display:grid;grid-template-columns:22px 1fr auto;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #1E3048}
.nextup-row:last-child{border-bottom:none}
.nextup-rank{font-size:.75rem;font-weight:700;color:#4BA8E8;text-align:center}
.nextup-name{font-size:.8rem;color:#EBF3FF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nextup-bar-wrap{grid-column:2;height:4px;background:#1E3048;border-radius:2px;overflow:hidden;margin-top:3px}
.nextup-bar-fill{height:100%;border-radius:2px;transition:width .4s ease}
.nextup-pct{font-size:.75rem;font-weight:600;white-space:nowrap}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}
@media(max-width:900px){.two-col{grid-template-columns:1fr}.kpi-strip{grid-template-columns:repeat(2,1fr)}}
@media(max-width:1100px) and (min-width:901px){.kpi-strip{grid-template-columns:repeat(4,1fr)}}
.chart-card{background:#182434;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.35);border:1px solid #243648}
.chart-card h2{font-size:.85rem;font-weight:600;color:#B8CEEA;margin-bottom:16px}
.chart-canvas-wrap{position:relative;height:160px}

/* team grid — full-width stacked */
.team-grid{display:flex;flex-direction:column;gap:10px;margin-bottom:24px}

/* person card */
.person-card{border:1px solid #243648;border-radius:10px;overflow:hidden;background:#182434;transition:border-color .15s,box-shadow .15s}
.person-card:hover{border-color:#3A82C4;box-shadow:0 2px 12px rgba(58,130,196,.2)}
.person-header{display:grid;grid-template-columns:190px 1fr 20px;align-items:center;gap:16px;padding:14px 20px;cursor:pointer;user-select:none}
@media(max-width:900px){.person-header{grid-template-columns:1fr;gap:10px}}
.person-name{font-size:.9rem;font-weight:600;color:#EBF3FF}
.person-title{font-size:.68rem;color:#6E8FAD;margin-top:3px}
.chevron{width:16px;height:16px;color:#6E8FAD;transition:transform .2s;justify-self:end}
.person-card.open .chevron{transform:rotate(180deg)}

/* mini capacity gauge */
.mini-gauge-track{height:5px;background:#1E3048;border-radius:3px;overflow:hidden;margin-top:8px}
.mini-gauge-fill{height:100%;border-radius:3px;transition:width .4s ease}
.green{background:#2E844A}.amber{background:#FE9339}.red-fill{background:#C23934}
.mini-gauge-label{font-size:.63rem;font-weight:600;margin-top:4px}
.caption-green{color:#4DB870}.caption-amber{color:#FE9339}.caption-red{color:#E05A55}
.no-hours-note{font-size:.63rem;color:#FE9339;margin-top:4px}

/* FY tile rows */
.fy-block{display:flex;flex-direction:column;gap:6px}
.fy-row{display:grid;grid-template-columns:36px repeat(7,1fr);gap:6px;align-items:stretch}
.fy-tile-empty{background:transparent;border-color:transparent}
.fy-row-label{font-size:.65rem;font-weight:700;letter-spacing:.06em;color:#4BA8E8;white-space:nowrap;display:flex;align-items:center}
.fy-tile{background:#0F1E2E;border:1px solid #1E3048;border-radius:6px;padding:6px 8px;text-align:center}
.fy-tile-label{font-size:.55rem;text-transform:uppercase;letter-spacing:.04em;color:#6E8FAD;white-space:nowrap}
.fy-tile-value{font-size:.82rem;font-weight:600;color:#D8E4F0;margin-top:2px}
.fy-tile-booked{background:#0A1F14;border-color:#1E4030}
.fy-tile-booked .fy-tile-label{color:#5BA887}
.fy-tile-booked .fy-tile-value{color:#3FBA7F}

/* DSR panel */
.dsr-panel{display:none;border-top:1px solid #1E3048;background:#0F1823;padding:14px 20px}
.person-card.open .dsr-panel{display:block}
.fy-cell-header{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#FFFFFF;padding:16px 6px 5px;border-bottom:1.5px solid #243648;background:#1A3A5C}
.dsr-table tbody tr:first-child .fy-cell-header{padding-top:4px}
.dsr-status-msg{font-size:.75rem;color:#6E8FAD}
.dsr-table{width:100%;border-collapse:collapse;font-size:.72rem;margin-top:8px}
.dsr-table th{text-align:left;color:#6E8FAD;font-weight:600;text-transform:uppercase;letter-spacing:.04em;padding:4px 6px;border-bottom:1.5px solid #243648}
.dsr-table td{padding:6px 6px;border-bottom:1px solid #182434;vertical-align:middle;color:#C8D8EC}
.dsr-table tr:last-child td{border-bottom:none}
.trunc{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge{display:inline-block;padding:2px 6px;border-radius:4px;font-size:.65rem;font-weight:600;white-space:nowrap}
.badge-booked{background:#0E3320;color:#4DB870}
.badge-proposal{background:#0A2040;color:#4BA8E8}
.badge-scoping{background:#332510;color:#E89A30}
.badge-lost{background:#330E0C;color:#E05A55}
.badge-other{background:#1E2E3E;color:#8AAAC4}
.sf-link{color:#4BA8E8;text-decoration:none}
.sf-link:hover{text-decoration:underline;color:#7DC2F5}

/* accordion */
.accordion{background:#182434;border:1px solid #243648;border-radius:10px;margin-bottom:16px;overflow:hidden}
.accordion-header{width:100%;background:transparent;border:none;color:#D8E4F0;display:flex;align-items:center;justify-content:space-between;padding:14px 20px;cursor:pointer;font-size:.88rem;font-weight:600;letter-spacing:.02em;text-align:left}
.accordion-header:hover{background:rgba(255,255,255,.05)}
.acc-chevron{width:16px;height:16px;flex-shrink:0;transition:transform .2s;color:#6E8FAD}
.accordion.open .acc-chevron{transform:rotate(180deg)}
.accordion-body{padding:16px 20px 20px;border-top:1px solid #243648}
.accordion:not(.open) .accordion-body{display:none}
.accordion-body .kpi-strip{margin-bottom:0}
.accordion-body .member-filter-card{margin-bottom:0;border:none;padding:0;background:transparent}

/* burning hot */
.burning-hot-card{background:#182434;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.35);border:1px solid #243648}
.burning-hot-card h2{font-size:.85rem;font-weight:600;color:#E8B4B4;margin-bottom:4px}
.burning-subtitle{font-size:.68rem;color:#8B5454;margin-bottom:14px}
.burning-rank{color:#E05A55}
.burning-fill{background:#C23934}
.burning-pct{color:#E05A55}
</style>
</head>
<body>

<header>
  <div>
    <h1>REG FINS GTM &mdash; Team Capacity Dashboard</h1>
    <div class="subtitle">FY27 &ndash; FY28 &bull; Financial Services &bull; REG FINS Shared Team</div>
  </div>
  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
    <button class="refresh-btn" id="refresh-btn" onclick="refreshData()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
      </svg>
      Refresh Data
    </button>
    <div class="last-updated" id="last-updated">Loading&hellip;</div>
  </div>
</header>

<main>

  <!-- 1. Overall Performance -->
  <div class="accordion open" id="acc-overall">
    <button class="accordion-header" onclick="toggleAccordion('acc-overall')">
      Overall Performance
      <svg class="acc-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
    <div class="accordion-body">
      <div class="kpi-strip">
        <div class="kpi-card kpi-card-booked">
          <div class="kpi-label">FY27 Booked Coverage &mdash; Net</div>
          <div class="kpi-value" id="kpi-booked-net">&mdash;</div>
          <div class="kpi-sub">Booked opps, net amount</div>
        </div>
        <div class="kpi-card kpi-card-booked">
          <div class="kpi-label">FY27 Booked Coverage &mdash; Gross</div>
          <div class="kpi-value" id="kpi-booked-gross">&mdash;</div>
          <div class="kpi-sub">Booked opps, gross bookings</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Net Pipeline Value</div>
          <div class="kpi-value" id="kpi-pipeline">&mdash;</div>
          <div class="kpi-sub">Opp Amount &mdash; FY27+FY28</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Gross Pipeline Value</div>
          <div class="kpi-value" id="kpi-gross">&mdash;</div>
          <div class="kpi-sub">Gross Bookings &mdash; FY27+FY28</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Active Engagements</div>
          <div class="kpi-value" id="kpi-dsrs">&mdash;</div>
          <div class="kpi-sub">Working + In Queue DSRs</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Hours Committed</div>
          <div class="kpi-value" id="kpi-hours">&mdash;</div>
          <div class="kpi-sub">Estimated hours logged</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Team Members</div>
          <div class="kpi-value" id="kpi-team">&mdash;</div>
          <div class="kpi-sub">Solutions directors</div>
        </div>
      </div>
    </div>
  </div>

  <!-- 2. Team Member Filters -->
  <div class="accordion open" id="acc-filter">
    <button class="accordion-header" onclick="toggleAccordion('acc-filter')">
      Team Member Filters
      <svg class="acc-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
    <div class="accordion-body">
      <div class="member-filter-card">
        <div class="member-filter-grid" id="member-filter"></div>
      </div>
    </div>
  </div>

  <!-- 3. Capacity Reporting -->
  <div class="accordion open" id="acc-capacity">
    <button class="accordion-header" onclick="toggleAccordion('acc-capacity')">
      Capacity Reporting
      <svg class="acc-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
    <div class="accordion-body">
      <div class="forecast-row" style="margin-bottom:16px">
        <div class="forecast-card">
          <h2>Team Capacity Forecast &mdash; Weekly Commitment vs. Available Hours</h2>
          <canvas id="forecast-chart" height="90"></canvas>
        </div>
        <div class="nextup-card">
          <h2>Next Up</h2>
          <div class="nextup-subtitle">Most available capacity &mdash; filtered team</div>
          <div id="nextup-list"></div>
        </div>
      </div>
      <div class="forecast-row">
        <div class="chart-card">
          <h2>Hours Committed vs. Spent by Person</h2>
          <div class="chart-canvas-wrap"><canvas id="hours-chart"></canvas></div>
        </div>
        <div class="burning-hot-card">
          <h2>Burning Hot</h2>
          <div class="burning-subtitle">Least remaining capacity &mdash; filtered team</div>
          <div id="burninghot-list"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 4. Business Performance -->
  <div class="accordion open" id="acc-business">
    <button class="accordion-header" onclick="toggleAccordion('acc-business')">
      Business Performance
      <svg class="acc-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
    <div class="accordion-body">
      <div class="two-col">
        <div class="chart-card">
          <h2>Pipeline Value by Month (FY27–FY28)</h2>
          <div class="chart-canvas-wrap" style="height:200px"><canvas id="pipeline-chart"></canvas></div>
        </div>
        <div class="chart-card">
          <h2>Monthly Booked (FY27–FY28)</h2>
          <div class="chart-canvas-wrap" style="height:200px"><canvas id="booked-chart"></canvas></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 5. Performance by Team Member -->
  <div class="accordion open" id="acc-team">
    <button class="accordion-header" onclick="toggleAccordion('acc-team')">
      Performance by Team Member
      <svg class="acc-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
    <div class="accordion-body">
      <div class="team-grid" id="team-grid"></div>
    </div>
  </div>

</main>

<script>
// All Salesforce-sourced strings are inserted via node.textContent, never innerHTML.
// The only innerHTML calls below build static DOM structure using only literal strings
// and numeric values computed locally.

const SF_BASE = 'https://org62.lightning.force.com';
let pipelineChart, hoursChart, forecastChart, bookedChart;
let activePersonIds = new Set();

// ── Safe DOM helpers ─────────────────────────────────────────
function txt(el, s) { el.textContent = String(s == null ? '' : s); }
function el(tag, cls) { const n = document.createElement(tag); if (cls) n.className = cls; return n; }
function div(cls) { return el('div', cls); }
function span(cls) { return el('span', cls); }

// ── Format helpers ───────────────────────────────────────────
function fmtM(v) {
  v = +v || 0;
  if (v >= 1e9) return '$' + (v/1e9).toFixed(1) + 'B';
  if (v >= 1e6) return '$' + (v/1e6).toFixed(1) + 'M';
  if (v >= 1e3) return '$' + (v/1e3).toFixed(0) + 'K';
  return '$' + Math.round(v);
}
function fmtDate(d) {
  if (!d) return '—';
  const parts = d.split('-');
  const months = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return months[+parts[1]] + ' ' + parts[2] + ', ' + parts[0];
}
function pctColor(pct) {
  if (pct > 90) return 'red';
  if (pct > 60) return 'amber';
  return 'green';
}
function stageCls(stage) {
  if (!stage) return 'badge-other';
  if (/booked|06/i.test(stage))   return 'badge-booked';
  if (/proposal|03/i.test(stage)) return 'badge-proposal';
  if (/scoping|02/i.test(stage))  return 'badge-scoping';
  if (/lost|dead/i.test(stage))   return 'badge-lost';
  return 'badge-other';
}
function stageLabel(stage) {
  if (!stage) return '—';
  if (/booked|06/i.test(stage))   return 'Booked';
  if (/proposal|03/i.test(stage)) return 'Proposal';
  if (/scoping|02/i.test(stage))  return 'Scoping';
  if (/lost|dead/i.test(stage))   return 'Lost';
  return stage.replace(/^\d+\s*-\s*/, '').slice(0, 20);
}

// ── Render KPIs ──────────────────────────────────────────────
function renderKPIs(data) {
  const t = data.team;
  const pipeline = t.reduce((s, p) => s + p.pipelineValue, 0);
  const gross    = t.reduce((s, p) => s + (p.grossBookings || 0), 0);
  const dsrs     = t.reduce((s, p) => s + p.activeDSRs, 0);
  const hours    = t.reduce((s, p) => s + p.estimatedHours, 0);

  const fy27booked = (data.monthlyBooked || []).filter(m => m.fiscal_label && m.fiscal_label.startsWith('FY27'));
  const fy27net   = fy27booked.reduce((s, m) => s + (m.net_booked   || 0), 0);
  const fy27gross = fy27booked.reduce((s, m) => s + (m.gross_booked || 0), 0);

  txt(document.getElementById('kpi-pipeline'),    fmtM(pipeline));
  txt(document.getElementById('kpi-gross'),        fmtM(gross));
  txt(document.getElementById('kpi-dsrs'),         dsrs);
  txt(document.getElementById('kpi-hours'),        hours > 0 ? hours.toFixed(0) + ' h' : '—');
  txt(document.getElementById('kpi-team'),         t.length);
  txt(document.getElementById('kpi-booked-net'),   fmtM(fy27net));
  txt(document.getElementById('kpi-booked-gross'), fmtM(fy27gross));

  const ts = new Date(data.lastRefreshed);
  const luEl = document.getElementById('last-updated');
  luEl.textContent = 'Salesforce data as of ' + ts.toLocaleString() + ' — to pull fresh data, ask Claude Code to "refresh the dashboard"';
  if (data.seeded) {
    const pill = span('seeded-pill');
    txt(pill, 'OFFLINE');
    luEl.appendChild(pill);
  }
}

// ── Render team grid ─────────────────────────────────────────
const _dsrLoaded = {};

function renderTeamGrid(data) {
  const grid = document.getElementById('team-grid');
  grid.textContent = '';
  const sorted = [...data.team].sort((a, b) => a.name.localeCompare(b.name));
  sorted.forEach(person => buildPersonCard(grid, person));
}

function buildPersonCard(container, person) {
  const hrs   = person.estimatedHours;
  const pct   = hrs > 0 ? Math.min(Math.round(hrs / 40 * 100), 150) : 0;
  const color = hrs > 0 ? pctColor(pct) : 'green';
  const fill  = Math.min(pct, 100);
  const open  = Math.max(0, 40 - hrs);

  const card = div('person-card');
  card.dataset.personId = person.id;

  // Header: [left: name+gauge] [center: FY tiles] [chevron]
  const header = div('person-header');
  header.setAttribute('role', 'button');
  header.setAttribute('aria-expanded', 'false');

  // Left: name, title, mini capacity gauge
  const left = div('');
  const nameEl = div('person-name'); txt(nameEl, person.name); left.appendChild(nameEl);
  const titleEl = div('person-title'); txt(titleEl, person.title); left.appendChild(titleEl);
  const miniTrack = div('mini-gauge-track');
  const miniFill = div('mini-gauge-fill ' + (color === 'red' ? 'red-fill' : color));
  miniFill.style.width = fill + '%';
  miniTrack.appendChild(miniFill);
  left.appendChild(miniTrack);
  if (hrs > 0) {
    const miniLbl = div('mini-gauge-label caption-' + (color === 'red' ? 'red' : color));
    miniLbl.textContent = pct + '% · ' + hrs.toFixed(0) + ' h / 40 h · ' + open.toFixed(0) + ' h open';
    left.appendChild(miniLbl);
  } else {
    const miniLbl = div('no-hours-note'); txt(miniLbl, '⚠ No est. hours'); left.appendChild(miniLbl);
  }

  // Center: FY27 row + FY28 row, each with 5 metric tiles
  const fyBlock = div('fy-block');
  [['FY27', person.fy27 || {}], ['FY28', person.fy28 || {}]].forEach(([label, d]) => {
    const row = div('fy-row');
    const lbl = div('fy-row-label'); txt(lbl, label); row.appendChild(lbl);
    const bookedTiles = label === 'FY27'
      ? [['Net Booked', fmtM(d.netBooked || 0), 'fy-tile-booked'], ['Gross Booked', fmtM(d.grossBooked || 0), 'fy-tile-booked']]
      : [['', '', 'fy-tile-empty'], ['', '', 'fy-tile-empty']];
    const tiles = [
      ...bookedTiles,
      ['Net Pipeline',   fmtM(d.netPipeline   || 0), ''],
      ['Gross Pipeline', fmtM(d.grossPipeline  || 0), ''],
      ['Open ARIs',      String(d.ariCount     || 0), ''],
      ['Active DSRs',    String(d.activeDsrs   || 0), ''],
      ['Invested',       (d.investedHours || 0).toFixed(0) + ' h', ''],
    ];
    tiles.forEach(([tlbl, tval, extraClass]) => {
      const tile = div('fy-tile' + (extraClass ? ' ' + extraClass : ''));
      const l = div('fy-tile-label'); txt(l, tlbl); tile.appendChild(l);
      const v = div('fy-tile-value'); txt(v, tval); tile.appendChild(v);
      row.appendChild(tile);
    });
    fyBlock.appendChild(row);
  });

  // Chevron
  const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  chevron.setAttribute('class', 'chevron');
  chevron.setAttribute('viewBox', '0 0 24 24');
  chevron.setAttribute('fill', 'none');
  chevron.setAttribute('stroke', 'currentColor');
  chevron.setAttribute('stroke-width', '2.5');
  chevron.setAttribute('stroke-linecap', 'round');
  chevron.setAttribute('stroke-linejoin', 'round');
  const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  poly.setAttribute('points', '6 9 12 15 18 9');
  chevron.appendChild(poly);

  header.appendChild(left);
  header.appendChild(fyBlock);
  header.appendChild(chevron);
  header.addEventListener('click', () => toggleCard(card));

  const panel = div('dsr-panel');
  panel.id = 'panel-' + person.id;

  card.appendChild(header);
  card.appendChild(panel);
  container.appendChild(card);
}

function toggleCard(card) {
  const isOpen = card.classList.contains('open');
  card.classList.toggle('open', !isOpen);
  const header = card.querySelector('.person-header');
  header.setAttribute('aria-expanded', String(!isOpen));
  if (!isOpen) {
    const pid = card.dataset.personId;
    if (!_dsrLoaded[pid]) loadDSRs(pid);
  }
}

// ── Fiscal year helper (SF FY = Feb–Jan, e.g. FY27 = Feb 2026–Jan 2027) ──
function getFY(dateStr) {
  if (!dateStr) return 'Unknown';
  const parts = dateStr.split('-');
  const month = +parts[1];
  const year  = +parts[0];
  const fy = month >= 2 ? year + 1 : year;
  return 'FY' + String(fy).slice(-2);
}

// ── Load DSR details ─────────────────────────────────────────
async function loadDSRs(personId) {
  const panel = document.getElementById('panel-' + personId);
  panel.textContent = '';
  const msg = div('dsr-status-msg');
  txt(msg, 'Loading engagements…');
  panel.appendChild(msg);

  try {
    const res = await fetch('/api/person/' + encodeURIComponent(personId) + '/dsrs');
    if (!res.ok) { const t = await res.text(); throw new Error(t); }
    const { dsrs } = await res.json();
    _dsrLoaded[personId] = true;
    panel.textContent = '';

    // Filter out pre-FY27 records, then group by fiscal year
    const active = (dsrs || []).filter(d => d.closeDate >= '2026-02-01');

    if (active.length === 0) {
      const m2 = div('dsr-status-msg'); txt(m2, 'No active engagements found.'); panel.appendChild(m2);
      return;
    }

    // Group by FY and sort each group by close date ascending
    const byFY = {};
    active.forEach(d => { const fy = getFY(d.closeDate); (byFY[fy] = byFY[fy] || []).push(d); });
    const fyKeys = Object.keys(byFY).sort();
    fyKeys.forEach(fy => byFY[fy].sort((a, b) => (a.closeDate || '').localeCompare(b.closeDate || '')));

    // One table so all columns share the same widths across FY groups
    const table = document.createElement('table');
    table.className = 'dsr-table';
    const thead = table.createTHead();
    const hr = thead.insertRow();
    [['Open','center'],['DSR','left'],['Delivery','center'],['Account','left'],['Stage','left'],['Est. h','right'],['Spent h','right'],['Value','right'],['Close Date','left']].forEach(([h, align]) => {
      const th = document.createElement('th'); th.textContent = h; th.style.textAlign = align; hr.appendChild(th);
    });
    const tbody = table.createTBody();

    fyKeys.forEach(fy => {
      // FY group divider row (spans all columns)
      const groupRow = tbody.insertRow();
      const groupCell = groupRow.insertCell();
      groupCell.colSpan = 9;
      groupCell.className = 'fy-cell-header';
      groupCell.textContent = fy;

      byFY[fy].forEach(d => {
        const row = tbody.insertRow();
        const CLOSED_STATUSES = new Set(['Closed - Duplicate','Closed - No Response','Closed - Not Qualified','Closed - Resolved','Not Qualified']);
        const isClosed = /^Closed/i.test(d.status || '') || CLOSED_STATUSES.has(d.status || '');

        // Open indicator
        const tdOpen = row.insertCell(); tdOpen.style.textAlign = 'center';
        const openMark = span(isClosed ? 'badge badge-lost' : 'badge badge-booked');
        openMark.textContent = isClosed ? '✕' : '✓';
        tdOpen.appendChild(openMark);

        // DSR link — href uses whitelisted Salesforce base + validated ID from server
        const tdName = row.insertCell();
        const link = document.createElement('a');
        link.className = 'sf-link';
        link.href = SF_BASE + '/lightning/r/Deal_Support_Request__c/' + encodeURIComponent(d.id) + '/view';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = d.name;
        tdName.appendChild(link);

        // Delivery Expertise indicator
        const tdDel = row.insertCell(); tdDel.style.textAlign = 'center';
        if (d.requestType === 'Delivery Expertise') {
          const deliveryMark = span('badge badge-booked');
          deliveryMark.textContent = '✓';
          tdDel.appendChild(deliveryMark);
        }

        // Account (truncated via CSS class)
        const tdAcc = row.insertCell(); tdAcc.className = 'trunc'; tdAcc.textContent = d.account || '—';
        tdAcc.title = d.account || '';

        // Stage badge
        const tdStage = row.insertCell();
        const badge = span('badge ' + stageCls(d.stage));
        badge.textContent = stageLabel(d.stage);
        tdStage.appendChild(badge);

        // Numeric cells
        const tdEst = row.insertCell(); tdEst.style.textAlign = 'right';
        tdEst.textContent = d.estimatedHours > 0 ? d.estimatedHours.toFixed(0) : '—';

        const tdSpent = row.insertCell(); tdSpent.style.textAlign = 'right';
        tdSpent.textContent = d.spentHours > 0 ? d.spentHours.toFixed(0) : '—';

        const tdVal = row.insertCell(); tdVal.style.textAlign = 'right';
        tdVal.textContent = d.dealValue > 0 ? fmtM(d.dealValue) : '—';

        const tdDate = row.insertCell();
        tdDate.textContent = fmtDate(d.closeDate);
      });
    });

    panel.appendChild(table);
  } catch (e) {
    panel.textContent = '';
    const err = div('dsr-status-msg');
    err.textContent = 'Could not load engagements: ' + e.message;
    panel.appendChild(err);
  }
}

// ── Accordion toggle ─────────────────────────────────────────
function toggleAccordion(id) {
  document.getElementById(id).classList.toggle('open');
}

// ── Next Up tile ─────────────────────────────────────────────
function renderNextUp(data) {
  const list = document.getElementById('nextup-list');
  list.textContent = '';

  const ranked = data.team
    .filter(p => activePersonIds.has(p.id))
    .map(p => {
      const committed = p.estimatedHours > 0 ? Math.min(Math.round(p.estimatedHours / 40 * 100), 150) : 0;
      return { name: p.name, committed };
    })
    .sort((a, b) => a.committed - b.committed)
    .slice(0, 5);

  ranked.forEach((p, i) => {
    const available = Math.max(0, 100 - p.committed);
    const color = p.committed > 90 ? 'red' : p.committed > 80 ? 'amber' : 'green';
    const barColor = color === 'red' ? '#C23934' : color === 'amber' ? '#FE9339' : '#2E844A';
    const pctClass = color === 'red' ? 'caption-red' : color === 'amber' ? 'caption-amber' : 'caption-green';

    const row = div('nextup-row');

    const rank = div('nextup-rank');
    txt(rank, String(i + 1));
    row.appendChild(rank);

    const nameWrap = div('');
    const nameEl = div('nextup-name');
    txt(nameEl, p.name);
    nameWrap.appendChild(nameEl);
    const barWrap = div('nextup-bar-wrap');
    const barFill = div('nextup-bar-fill');
    barFill.style.width = available + '%';
    barFill.style.background = barColor;
    barWrap.appendChild(barFill);
    nameWrap.appendChild(barWrap);
    row.appendChild(nameWrap);

    const pctEl = div('nextup-pct ' + pctClass);
    txt(pctEl, available + '% avail');
    row.appendChild(pctEl);

    list.appendChild(row);
  });

  if (ranked.length === 0) {
    const msg = div('dsr-status-msg');
    txt(msg, 'No team members selected.');
    list.appendChild(msg);
  }
}

// ── Burning Hot tile ─────────────────────────────────────────
function renderBurningHot(data) {
  const list = document.getElementById('burninghot-list');
  list.textContent = '';

  const ranked = data.team
    .filter(p => activePersonIds.has(p.id))
    .map(p => {
      const committed = p.estimatedHours > 0 ? Math.min(Math.round(p.estimatedHours / 40 * 100), 150) : 0;
      return { name: p.name, committed };
    })
    .sort((a, b) => b.committed - a.committed)   // descending — most loaded first
    .slice(0, 5);

  if (ranked.length === 0) {
    const msg = div('dsr-status-msg'); txt(msg, 'No team members selected.'); list.appendChild(msg); return;
  }

  const maxCommitted = Math.max(...ranked.map(e => e.committed), 1);

  ranked.forEach((p, i) => {
    const row = div('nextup-row');

    const rank = div('nextup-rank burning-rank');
    txt(rank, String(i + 1));
    row.appendChild(rank);

    const nameWrap = div('');
    const nameEl = div('nextup-name');
    txt(nameEl, p.name);
    nameWrap.appendChild(nameEl);
    const barWrap = div('nextup-bar-wrap');
    const barFill = div('nextup-bar-fill burning-fill');
    barFill.style.width = Math.min(100, p.committed / maxCommitted * 100) + '%';
    barWrap.appendChild(barFill);
    nameWrap.appendChild(barWrap);
    row.appendChild(nameWrap);

    const pctEl = div('nextup-pct burning-pct');
    txt(pctEl, p.committed + '% committed');
    row.appendChild(pctEl);

    list.appendChild(row);
  });
}

// ── Member filter ─────────────────────────────────────────────
function renderMemberFilter(data) {
  const grid = document.getElementById('member-filter');
  grid.textContent = '';

  // Group by team, preserving alphabetical order within each group
  const groups = {};
  [...data.team]
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach(p => { (groups[p.group] = groups[p.group] || []).push(p); });

  Object.entries(groups).forEach(([groupName, members]) => {
    // Group label spanning all 5 columns
    const lbl = div('member-filter-group');
    txt(lbl, groupName + '’s Team');
    grid.appendChild(lbl);

    members.forEach(person => {
      const item = div('member-filter-item');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = true;
      cb.id = 'cb-' + person.id;
      cb.addEventListener('change', () => {
        if (cb.checked) activePersonIds.add(person.id);
        else activePersonIds.delete(person.id);
        renderForecastChart(data);
        renderHoursChart(data);
        renderNextUp(data);
        renderBurningHot(data);
      });
      const lbl2 = document.createElement('label');
      lbl2.htmlFor = 'cb-' + person.id;
      txt(lbl2, person.name);
      item.appendChild(cb);
      item.appendChild(lbl2);
      grid.appendChild(item);
    });
  });
}

// Recompute weekly forecast from raw DSRs for the currently active people
function computeFilteredWeeks(data) {
  const INACTIVE = /booked|06|lost|dead/i;
  const CLOSED_SET = new Set(['Closed - Duplicate','Closed - No Response','Closed - Not Qualified','Closed - Resolved','Not Qualified']);
  const isClosed = s => /^Closed/i.test(s || '') || CLOSED_SET.has(s || '');
  const activeDSRs = [];
  activePersonIds.forEach(pid => {
    (data.personDSRs[pid] || []).forEach(d => {
      if (INACTIVE.test(d.stage || '') && d.requestType !== 'Delivery Expertise') return;
      if (isClosed(d.status)) return;
      if (!d.estimatedHours || !d.closeDate) return;
      activeDSRs.push(d);
    });
  });
  const available = activePersonIds.size * 40;
  return (data.weeklyCapacity || []).map(w => {
    const committed = activeDSRs.reduce(
      (s, d) => d.closeDate >= w.weekStart ? s + d.estimatedHours : s, 0
    );
    return {
      weekStart: w.weekStart,
      committedHours: Math.round(committed * 10) / 10,
      availableHours: available,
      utilization: available > 0 ? Math.round(committed / available * 1000) / 10 : 0,
    };
  });
}

// ── Charts ───────────────────────────────────────────────────
function renderForecastChart(data) {
  if (forecastChart) forecastChart.destroy();
  const ctx = document.getElementById('forecast-chart');
  const wc = computeFilteredWeeks(data);
  if (!wc.length) return;

  // Format week label: "Nov 2", "Nov 9", ...
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function fmtWeek(iso) {
    const [y, m, d] = iso.split('-').map(Number);
    return monthNames[m - 1] + ' ' + d;
  }

  const labels    = wc.map(w => fmtWeek(w.weekStart));
  const util      = wc.map(w => w.utilization);
  const threshold90 = wc.map(() => 90);
  const threshold80 = wc.map(() => 80);

  const gridColor = 'rgba(255,255,255,.06)';
  const tickColor = '#6E8FAD';

  forecastChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: '% Committed',
          data: util,
          borderColor: '#1589EE',
          backgroundColor: 'rgba(21,137,238,.15)',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: true,
          tension: 0.3,
          order: 1,
        },
        {
          label: '90% (over-committed)',
          data: threshold90,
          borderColor: '#C23934',
          borderWidth: 1.5,
          borderDash: [5, 4],
          pointRadius: 0,
          fill: false,
          order: 2,
        },
        {
          label: '80% (healthy)',
          data: threshold80,
          borderColor: '#FE9339',
          borderWidth: 1.5,
          borderDash: [5, 4],
          pointRadius: 0,
          fill: false,
          order: 3,
        },
      ]
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          align: 'end',
          labels: { font: { size: 10 }, color: '#8AAAC4', boxWidth: 24, padding: 12 }
        },
        tooltip: {
          backgroundColor: '#0F1E2E',
          titleColor: '#D8E4F0',
          bodyColor: '#D8E4F0',
          borderColor: '#243648',
          borderWidth: 1,
          callbacks: {
            title: items => {
              const idx = items[0].dataIndex;
              const w = wc[idx];
              return fmtWeek(w.weekStart) + ' (wk of ' + w.weekStart + ')';
            },
            label: c => {
              if (c.datasetIndex === 0) {
                const w = wc[c.dataIndex];
                return ' ' + c.raw.toFixed(1) + '% — ' + w.committedHours + ' h / ' + w.availableHours + ' h';
              }
              return ' ' + c.raw + '% threshold';
            }
          }
        }
      },
      scales: {
        y: {
          min: 0,
          suggestedMax: 110,
          ticks: { callback: v => v + '%', font: { size: 10 }, color: tickColor, stepSize: 20 },
          grid: { color: gridColor }
        },
        x: {
          ticks: { font: { size: 10 }, color: tickColor, maxTicksLimit: 14, maxRotation: 0 },
          grid: { display: false }
        }
      }
    }
  });
}

function renderPipelineChart(data) {
  if (pipelineChart) pipelineChart.destroy();
  const ctx = document.getElementById('pipeline-chart');
  const monIdx = {Jan:0,Feb:1,Mar:2,Apr:3,May:4,Jun:5,Jul:6,Aug:7,Sep:8,Oct:9,Nov:10,Dec:11};
  const now = new Date();
  const cutoff = new Date(now.getFullYear(), now.getMonth(), 1);
  const months = (data.monthlyPipeline || []).filter(m => {
    const [mon, yr] = m.label.split(' ');
    return new Date(+yr, monIdx[mon], 1) >= cutoff;
  });
  // All label/value data from server; Chart.js renders to canvas (not DOM text), safe.
  pipelineChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months.map(m => m.label),
      datasets: [{
        label: 'Pipeline ($M)',
        data: months.map(m => +(m.pipeline_value / 1e6).toFixed(2)),
        backgroundColor: '#2E844A',
        borderRadius: 5,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#0F1E2E', titleColor: '#D8E4F0', bodyColor: '#D8E4F0', borderColor: '#243648', borderWidth: 1, callbacks: { label: c => ' $' + c.raw.toFixed(1) + 'M' } }
      },
      scales: {
        y: {
          ticks: { callback: v => '$' + v + 'M', font: { size: 10 }, color: '#6E8FAD' },
          grid: { color: 'rgba(255,255,255,.06)' }
        },
        x: { ticks: { font: { size: 10 }, color: '#6E8FAD' }, grid: { display: false } }
      }
    }
  });
}

function renderBookingsChart(data) {
  if (bookedChart) bookedChart.destroy();
  const ctx = document.getElementById('booked-chart');
  const monIdx = {Jan:0,Feb:1,Mar:2,Apr:3,May:4,Jun:5,Jul:6,Aug:7,Sep:8,Oct:9,Nov:10,Dec:11};
  const months = (data.monthlyBooked || []);
  if (!months.length) return;
  bookedChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months.map(m => m.label),
      datasets: [
        {
          label: 'Net Booked ($M)',
          data: months.map(m => +(m.net_booked / 1e6).toFixed(2)),
          backgroundColor: '#1589EE',
          borderRadius: 0,
          borderSkipped: false,
          stack: 'booked',
        },
        {
          label: 'Gross Premium ($M)',
          data: months.map(m => +(Math.max(0, m.gross_booked - m.net_booked) / 1e6).toFixed(2)),
          backgroundColor: '#5BB8FF',
          borderRadius: 5,
          borderSkipped: 'bottom',
          stack: 'booked',
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { font: { size: 10 }, color: '#8AAAC4' } },
        tooltip: {
          backgroundColor: '#0F1E2E', titleColor: '#D8E4F0', bodyColor: '#D8E4F0',
          borderColor: '#243648', borderWidth: 1,
          callbacks: {
            afterBody: items => {
              const m = months[items[0].dataIndex];
              return ['', ' Gross total: $' + (m.gross_booked / 1e6).toFixed(1) + 'M'];
            },
            label: c => ' ' + c.dataset.label + ': $' + c.raw.toFixed(1) + 'M',
          }
        }
      },
      scales: {
        x: { stacked: true, ticks: { font: { size: 10 }, color: '#6E8FAD' }, grid: { display: false } },
        y: { stacked: true, ticks: { callback: v => '$' + v + 'M', font: { size: 10 }, color: '#6E8FAD' }, grid: { color: 'rgba(255,255,255,.06)' } }
      }
    }
  });
}

function renderHoursChart(data) {
  if (hoursChart) hoursChart.destroy();
  const ctx = document.getElementById('hours-chart');
  const sorted = [...data.team]
    .filter(p => activePersonIds.has(p.id))
    .sort((a, b) => b.estimatedHours - a.estimatedHours);
  hoursChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(p => p.name.split(' ')[0]),
      datasets: [
        { label: 'Committed (est.)', data: sorted.map(p => p.estimatedHours), backgroundColor: '#1589EE', borderRadius: 3 },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { font: { size: 10 }, color: '#8AAAC4' } },
        tooltip: { backgroundColor: '#0F1E2E', titleColor: '#D8E4F0', bodyColor: '#D8E4F0', borderColor: '#243648', borderWidth: 1, callbacks: { label: c => ' ' + c.raw.toFixed(0) + ' h' } }
      },
      scales: {
        y: {
          ticks: { callback: v => v + ' h', font: { size: 10 }, color: '#6E8FAD' },
          grid: { color: 'rgba(255,255,255,.06)' }
        },
        x: { ticks: { font: { size: 10 }, color: '#6E8FAD' }, grid: { display: false } }
      }
    }
  });
}

// ── Data loading ─────────────────────────────────────────────
async function loadData() {
  try {
    const res = await fetch('/api/data');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    activePersonIds = new Set(data.team.map(p => p.id));
    renderKPIs(data);
    renderMemberFilter(data);
    renderNextUp(data);
    renderBurningHot(data);
    renderForecastChart(data);
    renderTeamGrid(data);
    renderPipelineChart(data);
    renderBookingsChart(data);
    renderHoursChart(data);
  } catch (e) {
    const lu = document.getElementById('last-updated');
    lu.textContent = 'Error loading data: ' + e.message;
  }
}

async function refreshData() {
  const btn = document.getElementById('refresh-btn');
  const luEl = document.getElementById('last-updated');
  btn.classList.add('loading');
  btn.disabled = true;
  try {
    const res = await fetch('/api/refresh', { method: 'POST' });
    const result = await res.json();
    if (result.ok) {
      Object.keys(_dsrLoaded).forEach(k => delete _dsrLoaded[k]);
      await loadData();
    } else {
      const luEl2 = document.getElementById('last-updated');
      luEl2.textContent = 'Reload failed — ' + (result.error || 'unknown error');
    }
  } catch (e) {
    luEl.textContent = 'Reload failed — ' + e.message;
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

loadData();
</script>
</body>
</html>"""


if __name__ == '__main__':
    print('=' * 55)
    print('  REG FINS GTM Team Capacity Dashboard')
    print('  Visit: http://localhost:8080')
    port = int(os.environ.get('PORT', 8080))
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    if host == '127.0.0.1':
        print('=' * 55)
        print('  REG FINS GTM Team Capacity Dashboard')
        print(f'  Visit: http://localhost:{port}')
        print('=' * 55)
        from threading import Timer
        import webbrowser
        Timer(1.2, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    app.run(host=host, port=port, debug=False)
