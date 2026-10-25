"""Loopback-only VeraOS dashboard, with truthful unqualified capability states."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from typing import Callable
from urllib.parse import urlsplit, parse_qs


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
#conversation-result{white-space:pre-wrap;overflow-wrap:anywhere}
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
<label id="message-label" for="message">No local cognition route is connected.</label>
<input id="message" type="text" maxlength="2048" disabled placeholder="Messages unavailable until a route is admitted">
<button id="send" type="button" disabled>Send</button>
<p id="conversation-result" role="status">No request submitted.</p>
<p class="muted">Source fixtures are not authenticated model admission. VeraOS will not silently select a provider.</p>
</section>
</main>
<script>
let conversationAvailable=false;
let sending=false;
let requestSequence=0;
let syntheticFixture=false;
let restoredOnce=false;
const randomHex=()=>Array.from(crypto.getRandomValues(new Uint8Array(16)),
 x=>x.toString(16).padStart(2,'0')).join('');
const CONVERSATION_KEY='veraos-local-conversation-v1';
const PENDING_KEY='veraos-local-pending-message-v1';
let conversationId=localStorage.getItem(CONVERSATION_KEY);
if(!conversationId || !/^console-[0-9a-f]{32}$/.test(conversationId)){
 conversationId='console-'+randomHex();
 localStorage.setItem(CONVERSATION_KEY,conversationId);
}

function updateControls(){
 const enabled=conversationAvailable&&!sending;
 document.getElementById('message').disabled=!enabled;
 document.getElementById('send').disabled=!enabled;
}
// HTTP status alone does not bind a task to the persisted Mono opener.
// Require independently recomputed source/task IDs, exact opener head, and
// a separate fresh read-only canonical history record before retiring UI
// retry evidence. This is local-source consistency, NOT user authentication.
async function sha256Hex(text){
 if(!crypto.subtle||typeof crypto.subtle.digest!=='function')throw new Error('hash unavailable');
 const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
 return Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');
}
async function noProviderAckMatches(payload,original){
 const a=payload&&payload.canonical_intake;
 if(!a||typeof a!=='object'||payload.status!=='BLOCKED'
    ||a.schema!=='VERAOS_CANONICAL_NO_PROVIDER_ACK_V1'
    ||a.canonical_status!=='PENDING_NO_ADMITTED_PROVIDER'
    ||a.origin_authenticated!==false
    ||a.conversation_id!==original.conversation_id
    ||a.message_id!==original.request_id||a.text!==original.task
    ||a.task_id!==payload.task_id
    ||!/^ui-[0-9a-f]{64}$/.test(a.task_id)
    ||!(/^[0-9a-f]{64}$/.test(a.source_digest))
    ||!(/^[0-9a-f]{64}$/.test(a.opened_head))
    ||a.task_journal_head!==a.opened_head)return false;
 try{
  const key='ui-'+await sha256Hex(JSON.stringify({
    conversation_id:original.conversation_id,message_id:original.request_id,
    schema:'VERAOS_LOCAL_MESSAGE_KEY_V1'
  }));
  const source=await sha256Hex(JSON.stringify({
    conversation_id:original.conversation_id,message_id:original.request_id,
    schema:'VERAOS_LOCAL_UI_INTAKE_SOURCE_V1',text:original.task
  }));
  if(a.task_id!==key||a.source_digest!==source)return false;
  const history=await fetch('/api/conversation/history?conversation_id='+
    encodeURIComponent(original.conversation_id),{cache:'no-store'});
  if(!history.ok)return false;
  const data=await history.json();
  if(data.schema!=='VERAOS_CANONICAL_CONVERSATION_HISTORY_V1'
    ||data.conversation_id!==original.conversation_id
    ||!Array.isArray(data.messages)||data.truncated!==false
    ||data.memory_admitted!==false||data.model_admitted!==false)return false;
  const found=data.messages.filter(m=>
    m.conversation_id===original.conversation_id
    &&m.message_id===original.request_id &&m.text===original.task
    &&m.task_id===key &&m.source_digest===source);
  if(found.length!==1)return false;
  const m=found[0];
  if(m.task_journal_head!==a.opened_head
    ||m.status!=='PENDING_NO_ADMITTED_PROVIDER'
    ||m.source_kind!=='UNTRUSTED_USER_INPUT'
    ||m.accepted_as_task_result!==false
    ||m.memory_admitted!==false)return false;
  const still=JSON.parse(localStorage.getItem(PENDING_KEY)||'null');
  return !!still&&still.conversation_id===original.conversation_id
     &&still.request_id===original.request_id&&still.task===original.task;
 }catch(error){return false}
}
async function sendMessage(){
 if(!conversationAvailable||sending)return;
 const input=document.getElementById('message');
 const task=input.value;
 const result=document.getElementById('conversation-result');
 // Mono #77 accepts the ORIGINAL literal or explicitly rejects it.
 // Never turn invalid whitespace into a different canonical task.
 if(!task||task!==task.trim()||task.length>2048){
  result.textContent='INVALID_LITERAL_TEXT — original user input not submitted';
  return;
 }
 let pending=null;
 try{pending=JSON.parse(localStorage.getItem(PENDING_KEY)||'null')}
 catch(error){
  result.textContent='OUTCOME_UNKNOWN_NO_REDISPATCH — unreadable pending message';
  return;
 }
 // A claimed/unknown original may ONLY be retried under the identical
 // conversation, request ID and literal. It cannot be displaced by a new send.
 if(pending!==null && (!pending || pending.conversation_id!==conversationId
   || pending.task!==task || typeof pending.request_id!=='string'
   || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$/.test(pending.request_id))){
  result.textContent='OUTCOME_UNKNOWN_NO_REDISPATCH — reconcile prior message first';
  return;
 }
 sending=true;updateControls();
 result.textContent='PENDING — awaiting local response';
 requestSequence++;
 const requestId=pending?pending.request_id:'ui-'+randomHex();
 localStorage.setItem(PENDING_KEY,JSON.stringify({
  conversation_id:conversationId,request_id:requestId,task:task
 }));
 try{
  const response=await fetch('/api/conversation',{
   method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({task:task,request_id:requestId,conversation_id:conversationId})
  });
  const payload=await response.json();
  if(!response.ok){result.textContent=payload.status||'HELD_OR_UNAVAILABLE';return}
  if(payload.status==='COMPLETED' && typeof payload.final_text==='string'){
    if(syntheticFixture&&payload.synthetic===true){
      // Fixture text is not canonical result provenance; retain UI source.
      result.textContent='SYNTHETIC DEVELOPMENT FIXTURE — NOT AN ADMITTED MODEL\\n'+payload.final_text;
    }else{
      result.textContent='HELD — unverified completion not displayed';
    }
  }else{
    let acknowledged=false;
    if(payload.status==='BLOCKED'){
      acknowledged=await noProviderAckMatches(payload,{
        conversation_id:conversationId,request_id:requestId,task:task
      });
      if(acknowledged)localStorage.removeItem(PENDING_KEY);
    }
    result.textContent=payload.status==='BLOCKED'
      ?(acknowledged?'HELD — canonical task recorded; no model authorized'
         :'OUTCOME_UNKNOWN_NO_REDISPATCH — unverified task acknowledgement')
      :(payload.status||'PENDING');
  }
 }catch(error){result.textContent='OUTCOME_UNKNOWN_NO_REDISPATCH — retain original message'}
 finally{sending=false;updateControls()}
}
document.getElementById('send').addEventListener('click',sendMessage);
document.getElementById('message').addEventListener('keydown',event=>{
 if(event.key==='Enter'){event.preventDefault();sendMessage()}
});
async function restoreHistory(){
 try{
  const r=await fetch('/api/conversation/history?conversation_id='+encodeURIComponent(conversationId),
                       {cache:'no-store'});
  if(!r.ok)return;
  const h=await r.json();
  if(h.schema!=='VERAOS_CANONICAL_CONVERSATION_HISTORY_V1')return;
  if(sending||!Array.isArray(h.messages)||!h.messages.length)return;
  const shown=h.messages.slice(-8).map(m=>
    '['+m.message_id+' | '+m.status+'] USER INPUT (UNVERIFIED): '+m.text);
  document.getElementById('conversation-result').textContent=
   'RECOVERED TASK EVIDENCE — NOT GOVERNED MEMORY\\n'+shown.join('\\n');
 }catch(error){ /* retained in Mono ledger; do not invent a recovery */ }
}
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
 syntheticFixture=s.conversation_fixture_available===true;
 conversationAvailable=s.conversation_intake_available===true || syntheticFixture;
 document.getElementById('message-label').textContent=conversationAvailable
  ? 'SOURCE FIXTURE ONLY — not an authenticated resident model'
  : 'Messages are recorded as tasks; model execution remains HELD.';
 updateControls();
 if(conversationAvailable&&!restoredOnce){restoredOnce=true;restoreHistory();}
}catch(error){
 document.getElementById('status').textContent='LOCAL SERVICE UNAVAILABLE';
 conversationAvailable=false;updateControls();
}
}
refresh();setInterval(refresh,3000);
</script>
</body>
</html>
"""


_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
_MAX_REQUEST_BYTES = 4096


def make_handler(
    status_provider: Callable[[], dict],
    *,
    conversation_handler: Callable[[str, str], dict] | None = None,
    history_handler: Callable[[str], list[dict]] | None = None,
):
    """Loopback UI. HTTP input contains text and ID, never provider credentials."""

    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            self.request.settimeout(5.0)
            super().setup()

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

        def send_json(self, code: int, payload: dict) -> None:
            self.send_bytes(
                code, json.dumps(payload, sort_keys=True).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_GET(self):
            if self.path == "/":
                self.send_bytes(200, DASHBOARD.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/status":
                self.send_json(200, status_provider())
            elif urlsplit(self.path).path == "/api/conversation/history":
                if history_handler is None:
                    self.send_json(503, {"status": "HELD_HISTORY_UNAVAILABLE"})
                    return
                expected = f"127.0.0.1:{self.server.server_port}"
                if self.headers.get("Host") != expected:
                    self.send_json(403, {"status": "HELD_WRONG_HOST"})
                    return
                try:
                    query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                    cid = query["conversation_id"]
                    if set(query) != {"conversation_id"} or len(cid) != 1 or (
                        _REQUEST_ID.fullmatch(cid[0]) is None
                    ):
                        raise ValueError("invalid conversation")
                    rows = history_handler(cid[0])
                except (ValueError, KeyError, TypeError):
                    self.send_json(400, {"status": "INVALID_CONVERSATION"})
                    return
                except Exception:
                    self.send_json(503, {"status": "HELD_HISTORY_INCONSISTENT"})
                    return
                self.send_json(200, {
                    "schema": "VERAOS_CANONICAL_CONVERSATION_HISTORY_V1",
                    "conversation_id": cid[0], "messages": rows[-64:],
                    "truncated": len(rows) > 64, "memory_admitted": False,
                    "model_admitted": False,
                })
            else:
                self.send_bytes(404, b"Not Found", "text/plain; charset=utf-8")

        def do_POST(self):
            if self.path == "/api/chat":
                # Preserve the legacy chat route's explicit method hold.
                # Only /api/conversation can reach governed task intake.
                self.send_json(405, {"status": "METHOD_NOT_ALLOWED"})
                return
            if self.path != "/api/conversation":
                self.send_json(404, {"status": "NOT_FOUND"})
                return
            if conversation_handler is None:
                self.send_json(503, {"status": "HELD_NO_ADMITTED_PROVIDER"})
                return
            # No cross-origin write from another site in an ordinary browser.
            # This is NOT authentication against other local processes.
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected:
                self.send_json(403, {"status": "HELD_WRONG_HOST"})
                return
            origin = self.headers.get("Origin")
            if origin != f"http://{expected}":
                self.send_json(403, {"status": "HELD_WRONG_ORIGIN"})
                return
            if self.headers.get("Content-Type", "").lower() != "application/json":
                self.send_json(415, {"status": "UNSUPPORTED_CONTENT_TYPE"})
                return
            size = self.headers.get("Content-Length", "")
            if len(size) > 6 or not size.isascii() or not size.isdecimal():
                self.send_json(411, {"status": "INVALID_LENGTH"})
                return
            count = int(size)
            if not 0 < count <= _MAX_REQUEST_BYTES:
                self.send_json(413, {"status": "REQUEST_TOO_LARGE"})
                return
            try:
                raw = self.rfile.read(count)
                request = json.loads(raw)
            except (ValueError, UnicodeError):
                self.send_json(400, {"status": "INVALID_JSON"})
                return
            if (type(request) is not dict
                or set(request) not in ({"task", "request_id"}, {"task", "request_id", "conversation_id"})
                or type(request["task"]) is not str
                or not request["task"].strip()
                or request["task"] != request["task"].strip()
                or len(request["task"]) > 2048
                or type(request["request_id"]) is not str
                or _REQUEST_ID.fullmatch(request["request_id"]) is None
                or ("conversation_id" in request and
                    (type(request["conversation_id"]) is not str
                     or _REQUEST_ID.fullmatch(request["conversation_id"]) is None))):
                self.send_json(400, {"status": "INVALID_REQUEST"})
                return
            try:
                answer = conversation_handler(
                    request["task"], request["request_id"],
                    request["conversation_id"],
                ) if "conversation_id" in request else conversation_handler(
                    request["task"], request["request_id"],
                )
            except (ValueError, RuntimeError):
                self.send_json(503, {"status": "HELD_OR_UNAVAILABLE"})
                return
            except Exception:
                # No fabricated completion on unknown local model failure.
                self.send_json(502, {"status": "OUTCOME_UNKNOWN"})
                return
            if type(answer) is not dict or answer.get("status") not in {
                "PENDING", "COMPLETED", "FAILED", "BLOCKED", "CANCELLED",
            }:
                self.send_json(502, {"status": "OUTCOME_UNKNOWN"})
                return
            if answer["status"] == "COMPLETED":
                # A callback's status string cannot mint successful output.
                # The resident additionally verifies the durable Pre-Active
                # run/event/route before returning this terminal state.
                run_id = answer.get("run_id")
                text = answer.get("final_text")
                if (type(run_id) is not str or not run_id
                    or len(run_id) > 128
                    or type(text) is not str or not text.strip()
                    or len(text) > 8192):
                    self.send_json(502, {"status": "OUTCOME_UNKNOWN"})
                    return
            self.send_json(
                200 if answer["status"] == "COMPLETED" else 202,
                {
                    "status": answer["status"],
                    "request_id": request["request_id"],
                    "run_id": answer.get("run_id"),
                    "task_id": answer.get("task_id"),
                    "canonical_intake": (
                        answer.get("canonical_intake")
                        if answer["status"] == "BLOCKED" else None
                    ),
                    "synthetic": answer.get("synthetic") is True,
                    "accepted_as_task_result": False,
                    "model_authenticated": False,
                    "protected_effect_authority": False,
                    "final_text": answer.get("final_text") if answer["status"] == "COMPLETED" else None,
                },
            )

        def log_message(self, format, *args):
            return

    return Handler


def open_loopback_server(
    status_provider: Callable[[], dict],
    *,
    port: int = 18765,
    conversation_handler: Callable[[str, str], dict] | None = None,
    history_handler: Callable[[str], list[dict]] | None = None,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(
        ("127.0.0.1", port),
        make_handler(status_provider, conversation_handler=conversation_handler, history_handler=history_handler),
    )
