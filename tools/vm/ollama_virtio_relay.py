#!/usr/bin/env python3
"""Source-bound QEMU VirtIO text relay; no host tools or arbitrary destinations.

Runs outside guest in a narrow Docker sidecar sharing QEMU's network namespace.
QEMU exposes a chardev Unix-domain socket in a private Docker volume; this
sidecar connects over that file while only it can reach Windows Ollama.
Guest has -nic none. Sidecar never listens or executes arbitrary operations.
"""
from __future__ import annotations
import argparse
import json
import re
import socket
import time
from urllib.parse import urlsplit
from urllib.request import build_opener,ProxyHandler,Request

MODEL="qwen3:4b-instruct"
MODEL_DIGEST="0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
MODEL_BYTES=2497293803
MAX_MODEL_BYTES=4_000_000_000
MAX_FRAME=8192
ID=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9:._-]{0,95}$")
ALLOWED_ROLES=frozenset(("user","assistant","system"))


class PinnedOllama:
    def __init__(self, base_url: str, model: str, digest: str, size: int):
        url=urlsplit(base_url)
        if (url.scheme!="http" or url.username or url.password or url.path not in ("","/")
                or url.query or url.fragment or url.hostname not in ("127.0.0.1","host.docker.internal")
                or (url.hostname=="host.docker.internal" and url.port!=11434)
                or url.port is None):
            raise ValueError("Only exact allowed local Ollama host endpoint")
        if model!=MODEL or digest!=MODEL_DIGEST or size!=MODEL_BYTES:
            raise ValueError("Pinned model identity mismatch")
        if not 0<size<MAX_MODEL_BYTES:
            raise ValueError("Model exceeds 4 GB cap")
        self.base_url=base_url.rstrip("/")
        self.model=model
        self.digest=digest
        self.size=size
        self.opener=build_opener(ProxyHandler({}))

    def _json(self, path: str, payload: dict|None=None) -> dict:
        data=json.dumps(payload,separators=(",",":")).encode() if payload is not None else None
        req=Request(self.base_url+path,data=data,method="POST" if data is not None else "GET")
        if data is not None:
            req.add_header("Content-Type","application/json")
        with self.opener.open(req,timeout=90) as resp:
            raw=resp.read(65537)
        if len(raw)>65536:
            raise RuntimeError("Ollama response exceeds limited size")
        result=json.loads(raw)
        if not isinstance(result,dict):
            raise RuntimeError("Ollama response is not an object")
        return result

    def verify(self) -> None:
        data=self._json("/api/tags")
        items=data.get("models")
        if not isinstance(items,list):
            raise RuntimeError("Ollama inventory unavailable")
        found=[m for m in items if isinstance(m,dict) and m.get("name")==self.model]
        if len(found)!=1:
            raise RuntimeError("Pinned model not found exactly once")
        m=found[0]
        if m.get("digest")!=self.digest or type(m.get("size")) is not int or m["size"]!=self.size:
            raise RuntimeError("Pinned model digest/size changed: deny inference")

    def handle(self, obj: dict) -> dict:
        if not isinstance(obj,dict):
            raise ValueError("Request must be object")
        ident=obj.get("id")
        if not isinstance(ident,str) or not ID.fullmatch(ident):
            raise ValueError("Invalid bounded request ID")
        op=obj.get("op")
        if op=="models":
            if set(obj)!={"op","id"}:
                raise ValueError("Unexpected model-request fields")
            self.verify()
            return {"id":ident,"ok":True,"models":[self.model]}
        if op!="chat" or set(obj)!={"op","id","model","messages"}:
            raise ValueError("Only bounded text chat and model inventory supported")
        if obj["model"]!=self.model:
            raise ValueError("Requested model differs from pinned identity")
        messages=obj["messages"]
        if not isinstance(messages,list) or not 1<=len(messages)<=12:
            raise ValueError("Invalid message count")
        normalized=[]
        for message in messages:
            if not isinstance(message,dict) or set(message)!={"role","content"}:
                raise ValueError("Unexpected message fields")
            if message["role"] not in ALLOWED_ROLES or not isinstance(message["content"],str):
                raise ValueError("Role or text invalid")
            if not message["content"] or len(message["content"])>5000:
                raise ValueError("Message length invalid")
            normalized.append(message)
        if normalized[-1]["role"]!="user" or sum(len(x["content"]) for x in normalized)>6000:
            raise ValueError("Unbounded or incomplete user request")
        self.verify()
        reply=self._json("/api/chat",{
            "model":self.model,"stream":False,"messages":normalized,
            "options":{"num_ctx":2048,"num_predict":64,"temperature":0.0},
            "keep_alive":"0",
        })
        if reply.get("done") is not True or not isinstance(reply.get("message"),dict):
            raise RuntimeError("Incomplete Ollama model response")
        message=reply["message"]
        if message.get("role")!="assistant" or not isinstance(message.get("content"),str):
            raise RuntimeError("Ollama did not return assistant text")
        answer=message["content"]
        if not 0<len(answer)<=4000:
            raise RuntimeError("Empty or oversized model output")
        if message.get("tool_calls"):
            raise RuntimeError("Tool calls are not permitted")
        return {"id":ident,"ok":True,"text":answer}


SOCKET_PATH="/modelbridge/virtio-model.sock"


def run_relay(path: str, model: PinnedOllama) -> None:
    if path!=SOCKET_PATH:
        raise ValueError("Only the private QEMU Unix chardev volume is allowed")
    model.verify()
    deadline=time.monotonic()+30
    while True:
        stream=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            stream.settimeout(3)
            stream.connect(path)
            break
        except (ConnectionRefusedError,TimeoutError,OSError):
            stream.close()
            if time.monotonic()>deadline:
                raise RuntimeError("Private QEMU Unix chardev not accepting relay")
            time.sleep(0.5)
    print("VERAOS_RELAY_CONNECTED_PINNED_MODEL",flush=True)
    with stream:
        stream.settimeout(120)
        with stream.makefile("rwb",buffering=0) as wire:
            while True:
                frame=wire.readline(MAX_FRAME+2)
                if not frame:
                    return
                ident=None
                try:
                    if len(frame)>MAX_FRAME or not frame.endswith(b"\n"):
                        raise ValueError("Oversized/malformed frame")
                    obj=json.loads(frame)
                    if isinstance(obj,dict) and isinstance(obj.get("id"),str):
                        ident=obj["id"][:96]
                    response=model.handle(obj)
                except Exception as exc:
                    response={"id":ident,"ok":False,"error":str(exc)[:150]}
                data=json.dumps(response,separators=(",",":")).encode()+b"\n"
                if len(data)>MAX_FRAME:
                    data=b'{"id":null,"ok":false,"error":"response too long"}\n'
                wire.write(data)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--socket-path",default=SOCKET_PATH)
    parser.add_argument("--ollama",default="http://host.docker.internal:11434")
    args=parser.parse_args()
    run_relay(args.socket_path,PinnedOllama(args.ollama,MODEL,MODEL_DIGEST,MODEL_BYTES))


if __name__=="__main__":
    main()
