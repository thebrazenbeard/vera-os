"""Guest-side bounded VirtIO serial RPC and loopback-only text adapter.

Opt-in development/qualification transport. The normal resident does not
start this endpoint, and this module grants no model/identity/effect authority.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import select
import threading
import time

MODEL="qwen3:4b-instruct"
PORT_NAME="org.veraos.model.v1"
MAX_FRAME=8192
_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,95}$")


def find_port(sysfs:Path=Path("/sys/class/virtio-ports"),dev:Path=Path("/dev")) -> Path:
    matched=[]
    for p in sysfs.glob("vport*"):
        try:
            if (p/"name").read_text().strip()==PORT_NAME:
                matched.append(dev/p.name)
        except OSError:
            continue
    if len(matched)!=1 or not matched[0].exists():
        raise RuntimeError("exact VirtIO model port not available")
    return matched[0]


class VirtioRPC:
    def __init__(self,fd:int,*,owned=False):
        self.fd=fd
        self.owned=owned
        self.lock=threading.Lock()
        self.pending=b""
    @classmethod
    def open(cls,path:Path):
        return cls(os.open(path,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK),owned=True)
    def close(self):
        if self.owned:
            os.close(self.fd)
            self.owned=False
    def call(self,obj:dict,*,timeout:float=100) -> dict:
        if not isinstance(obj,dict) or not isinstance(obj.get("id"),str) or not _ID.fullmatch(obj["id"]):
            raise ValueError("Invalid request identity")
        if timeout<=0 or timeout>120:
            raise ValueError("Invalid bounded time")
        raw=json.dumps(obj,separators=(",",":")).encode()+b"\n"
        if len(raw)>MAX_FRAME:
            raise ValueError("Request too large")
        with self.lock:
            deadline=time.monotonic()+timeout
            off=0
            while off<len(raw):
                left=deadline-time.monotonic()
                if left<=0 or not select.select([],[self.fd],[],left)[1]:
                    raise TimeoutError("VirtIO request write timed out")
                try:
                    off+=os.write(self.fd,raw[off:])
                except BlockingIOError:
                    continue
            while True:
                if b"\n" in self.pending:
                    frame,self.pending=self.pending.split(b"\n",1)
                    if len(frame)+1>MAX_FRAME:
                        raise RuntimeError("VirtIO response too long")
                    response=json.loads(frame)
                    if not isinstance(response,dict) or response.get("id")!=obj["id"]:
                        raise RuntimeError("Unexpected VirtIO reply identity")
                    if response.get("ok") is not True:
                        raise RuntimeError(str(response.get("error","relay refused"))[:180])
                    return response
                if len(self.pending)>=MAX_FRAME:
                    raise RuntimeError("VirtIO response too long")
                left=deadline-time.monotonic()
                if left<=0 or not select.select([self.fd],[],[],left)[0]:
                    raise TimeoutError("VirtIO response timeout")
                try:
                    data=os.read(self.fd,2048)
                except BlockingIOError:
                    continue
                if not data:
                    raise ConnectionError("VirtIO relay disconnected")
                self.pending+=data


def open_loopback_compat(rpc:VirtioRPC,*,port:int=18766) -> ThreadingHTTPServer:
    if not 0<=port<=65535:
        raise ValueError("Invalid loopback port")
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            return
        def send_json(self,code:int,payload:dict) -> None:
            body=json.dumps(payload,separators=(",",":")).encode()
            self.send_response(code)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            if self.path!="/v1/models":
                return self.send_json(404,{"error":"not found"})
            try:
                x=rpc.call({"op":"models","id":"guest-models-"+str(time.monotonic_ns())})
                if x.get("models")!=[MODEL]:
                    raise RuntimeError("exact pinned model absent")
                return self.send_json(200,{"data":[{"id":MODEL}]})
            except Exception:
                return self.send_json(503,{"error":"model not available"})
        def do_POST(self):
            if self.path!="/v1/chat/completions":
                return self.send_json(404,{"error":"not found"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 0<length<=MAX_FRAME:
                    return self.send_json(413,{"error":"invalid request size"})
                request=json.loads(self.rfile.read(length))
                if not isinstance(request,dict) or set(request)!={"model","messages"}:
                    raise ValueError("Only text inference payload accepted")
                if request["model"]!=MODEL:
                    raise ValueError("Model mismatch")
                result=rpc.call({"op":"chat","id":"guest-chat-"+str(time.monotonic_ns()),
                    "model":MODEL,"messages":request["messages"]})
                return self.send_json(200,{"choices":[{"message":{"role":"assistant","content":result["text"]}}]})
            except (ValueError,TypeError):
                return self.send_json(400,{"error":"invalid text-only request"})
            except Exception:
                return self.send_json(503,{"error":"model relay unavailable"})
    server=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    server.daemon_threads=True
    return server
