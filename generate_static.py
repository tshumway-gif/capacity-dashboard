"""
Generate a self-contained static HTML export of the capacity dashboard.
Embeds data.json inline so no server is needed.

Usage:
    python -I generate_static.py
    -> outputs: dashboard_export.html
"""
import json
import re
import sys
from pathlib import Path

BASE       = Path(r'C:\Users\tshumway\capacity-dashboard')
SERVER_PY  = BASE / 'server.py'
DATA_FILE  = BASE / 'data.json'
OUT_FILE   = BASE / 'dashboard_export.html'

# ── Extract HTML template from server.py ─────────────────────────
src = SERVER_PY.read_text(encoding='utf-8')
start = src.index('HTML = r"""') + len('HTML = r"""')
end   = src.index('"""', start)
html  = src[start:end]

# ── Load data ─────────────────────────────────────────────────────
with open(DATA_FILE, encoding='utf-8') as f:
    data = json.load(f)

data_js = json.dumps(data, ensure_ascii=False)

# ── Build fetch shim + inline data ───────────────────────────────
shim = f"""
<script>
// Static export — all API calls are served from inline data
(function() {{
  var __D = {data_js};
  var _orig = window.fetch.bind(window);
  window.fetch = function(url, opts) {{
    if (url === '/api/data') {{
      return Promise.resolve({{ ok: true, json: function() {{ return Promise.resolve(__D); }} }});
    }}
    var dsr_m = url.match(/^\\/api\\/person\\/([^\\/]+)\\/dsrs$/);
    if (dsr_m) {{
      var pid = decodeURIComponent(dsr_m[1]);
      var dsrs = (__D.personDSRs || {{}})[pid] || [];
      return Promise.resolve({{ ok: true, json: function() {{ return Promise.resolve({{ dsrs: dsrs }}); }} }});
    }}
    if (url === '/api/refresh') {{
      return Promise.resolve({{ ok: true, json: function() {{ return Promise.resolve({{ ok: false, error: 'Refresh not available in static export. Regenerate dashboard_export.html via Claude Code.' }}); }} }});
    }}
    return _orig(url, opts);
  }};
}})();
</script>
"""

# ── Inject shim just before </body> ──────────────────────────────
if '</body>' not in html:
    print('ERROR: could not find </body> in HTML template', file=sys.stderr)
    sys.exit(1)

html = html.replace('</body>', shim + '\n</body>', 1)

# ── Update the "last updated" footer note for static context ─────
html = html.replace(
    'to pull fresh data, ask Claude Code to &quot;refresh the dashboard&quot;',
    'static export — to update, ask Claude Code to regenerate dashboard_export.html'
)

OUT_FILE.write_text(html, encoding='utf-8')
print(f'Export written to: {OUT_FILE}')
print(f'File size: {OUT_FILE.stat().st_size / 1024:.0f} KB')
print('Upload dashboard_export.html to Bitsoma (no server required).')
