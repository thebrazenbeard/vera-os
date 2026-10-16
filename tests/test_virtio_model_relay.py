"""Adversarial tests of the pinned sub-4GB, text-only QEMU serial relay."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import importlib.util,json,socket,threading
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ollama_virtio_relay",ROOT/"tools/vm/ollama_virtio_relay.py")
assert spec is not None

def get_module():
    module=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

PIN_NAME="qwen3:4b-instruct"
PIN_DIGEST="0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
PIN_SIZE=2497293803

@contextmanager
def fake_ollama(*,digest=PIN_DIGEST,size=PIN_SIZE):
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path=="/api/tags"
            result={"models":[{"name":PIN_NAME,"size":size,"digest":digest}]}
            data=json.dumps(result).encode()
            self.send_response(200);self.send_header("Content-Length",str(len(data)));self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            assert self.path=="/api/chat"
            obj=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(obj)
            data=json.dumps({"message":{"role":"assistant","content":"Real model test answer"},"done":True}).encode()
            self.send_response(200);self.send_header("Content-Length",str(len(data)));self.end_headers()
            self.wfile.write(data)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:yield "http://127.0.0.1:%d"%server.server_port,calls
    finally:server.shutdown();server.server_close();t.join(2)

def test_exact_model_digest_and_strict_size():
    r=get_module()
    with fake_ollama() as (url,calls):
        b=r.PinnedOllama(url,PIN_NAME,PIN_DIGEST,PIN_SIZE)
        assert b.handle({"op":"models","id":"m1"})=={
            "id":"m1","ok":True,"models":[PIN_NAME],
        }
        result=b.handle({"op":"chat","id":"c1","model":PIN_NAME,
            "messages":[{"role":"user","content":"Say hello"}]})
        assert result["ok"] is True
        assert result["text"]=="Real model test answer"
        assert len(calls)==1
        assert calls[0]["model"]==PIN_NAME
        assert calls[0]["stream"] is False
        assert "tools" not in calls[0]
        assert calls[0]["options"]["num_predict"]<=80
    for fake_kw in ({"digest":"f"*64},{"size":4500000000}):
        with fake_ollama(**fake_kw) as (url,calls):
            b=r.PinnedOllama(url,PIN_NAME,PIN_DIGEST,PIN_SIZE)
            with pytest.raises((RuntimeError,ValueError)):
                b.handle({"op":"models","id":"x"})
            assert calls==[]

def test_relay_rejects_ambient_urls_tools_and_large_prompts():
    r=get_module()
    with fake_ollama() as (url,calls):
        b=r.PinnedOllama(url,PIN_NAME,PIN_DIGEST,PIN_SIZE)
        inputs=[
            {"op":"curl","id":"a","url":"https://example.com"},
            {"op":"chat","id":"b","model":"ministral-3:14b","messages":[{"role":"user","content":"hello"}]},
            {"op":"chat","id":"c","model":PIN_NAME,"messages":[{"role":"tool","content":"run"}]},
            {"op":"chat","id":"d","model":PIN_NAME,"messages":[{"role":"user","content":"x"*8000}]},
            {"op":"chat","id":"e","model":PIN_NAME,"messages":[{"role":"user","content":"hi"}],"tools":[{"name":"shell"}]},
            {"op":"models","id":"f","url":"http://169.254.169.254"},
        ]
        for inp in inputs:
            with pytest.raises((ValueError,RuntimeError)):
                b.handle(inp)
        assert calls==[]

def test_fixed_model_policy_refuses_bad_endpoints():
    r=get_module()
    for url in ("https://example.org","http://169.254.169.254:11434","http://host.docker.internal:80","file:///tmp/x"):
        with pytest.raises(ValueError):
            r.PinnedOllama(url,PIN_NAME,PIN_DIGEST,PIN_SIZE)

def test_malformed_frames_or_mismatched_schema_refused():
    r=get_module()
    for value in (b"garbage",b"[]" , b'{"op":"models","id":"m1","extra":1}',b'{"op":"chat","id":"x","messages":"oops"}'):
        try:
            parsed=json.loads(value)
        except ValueError:
            continue
        with fake_ollama() as (url,calls):
            b=r.PinnedOllama(url,PIN_NAME,PIN_DIGEST,PIN_SIZE)
            with pytest.raises((ValueError,RuntimeError,TypeError)):
                b.handle(parsed)


def test_chardev_uses_private_unix_socket_only():
    r=get_module()
    with fake_ollama() as (url,calls):
        model=r.PinnedOllama(url,PIN_NAME,PIN_DIGEST,PIN_SIZE)
        for path in ("127.0.0.1:17980","/tmp/other.sock","/modelbridge/../host.sock"):
            with pytest.raises(ValueError,match="private"):
                r.run_relay(path,model)
        assert r.SOCKET_PATH=="/modelbridge/virtio-model.sock"
