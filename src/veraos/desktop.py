"""Loopback-only VeraOS dashboard, with truthful unqualified capability states."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Callable


DASHBOARD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VeraOS — Resident Console</title>
<style>
:root{color-scheme:dark;font:16px/1.5 system-ui,sans-serif;background:#101b23;color:#e6f0f4}
*{box-sizing:border-box}body{margin:0;min-height:100vh}
header{padding:24px max(24px,5vw);background:#172b35;border-bottom:1px solid #2d4b57}
h1{font-size:1.65rem;margin:0;letter-spacing:.08em}h2{font-size:1.1rem}
main{max-width:1000px;margin:auto;padding:28px 24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:16px}
section{border:1px solid #36505a;border-radius:12px;background:#1b313c;padding:20px;margin-bottom:16px}
.state{font-family:ui-monospace,monospace;font-weight:600;overflow-wrap:anywhere}
small,.muted{color:#a9c0c9}.notice{padding:10px 14px;border-left:3px solid #b5d19b;background:#263e41}
label{display:block;margin-bottom:10px}input{background:#182731;color:#a9c0c9;border:1px solid #36505a;padding:12px;width:100%;border-radius:8px}
button{background:#36505a;color:#ccd9df;border:0;border-radius:8px;padding:12px;margin-top:8px}
button:disabled{cursor:not-allowed;opacity:.55}ul{padding-left:19px}
</style>
</head>
<body>
<header><h1>VERA OS</h1><small>Private resident environment · Local-only console</small></header>
<main>
<div class="notice">Live system telemetry; availability is not authorization.</div>
<section>
<h2>Resident runtime</h2>
<p id="status" class="state" role="status">Checking local resident host…</p>
<p class="muted">COMPOSED_NO_COGNITION means the component host is active but no cognition route has been admitted.</p>
</section>
<div class="grid">
<section><h2>Resident components</h2><ul id="components"><li>Loading…</li></ul></section>
<section><h2>Capabilities</h2>
<p>Canonical Vera runtime: <span id="canonical" class="state">UNVERIFIED</span></p>
<p>Local cognition: <span id="cognition" class="state">UNVERIFIED</span></p>
<p>Protected effects: <span id="effects" class="state">DENIED</span></p>
</section>
</div>
<section>
<h2>Conversation</h2>
<label for="message">No local cognition route is connected.</label>
<input id="message" type="text" disabled placeholder="Messages unavailable until a route is admitted">
<button disabled>Send</button>
<p class="muted">VeraOS will not simulate a model response or silently select a paid provider.</p>
</section>
</main>
<script>
async function refresh(){
try{
 const response=await fetch('/api/status',{cache:'no-store'});
 if(!response.ok)throw new Error('HTTP '+response.status);
 const s=await response.json();
 document.getElementById('status').textContent=s.status||'UNVERIFIED';
 document.getElementById('components').replaceChildren(
  ...(s.components||[]).map(name=>{const li=document.createElement('li');li.textContent=name;return li})
 );
 document.getElementById('canonical').textContent=s.canonical_runtime_qualified?'QUALIFIED':'UNQUALIFIED';
 document.getElementById('cognition').textContent=s.cognition_route_qualified?'AVAILABLE':'NO ROUTE';
 document.getElementById('effects').textContent=s.protected_effect_authority?'AUTHORIZED':'DENIED';
}catch(error){document.getElementById('status').textContent='LOCAL SERVICE UNAVAILABLE';}
}
refresh();setInterval(refresh,3000);
</script>
</body>
</html>
"""


def make_handler(status_provider: Callable[[], dict]):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; connect-src 'self'; script-src 'unsafe-inline'; "
                "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.send_bytes(200, DASHBOARD.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/status":
                data = json.dumps(status_provider(), sort_keys=True).encode("utf-8")
                self.send_bytes(200, data, "application/json")
            else:
                self.send_bytes(404, b"Not Found", "text/plain; charset=utf-8")

        def do_POST(self):
            self.send_bytes(405, b"Read-only local console", "text/plain; charset=utf-8")

        def log_message(self, format, *args):
            return

    return Handler


def open_loopback_server(
    status_provider: Callable[[], dict],
    *,
    port: int = 18765,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(status_provider))
