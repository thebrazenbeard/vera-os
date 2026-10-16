"""Guest loopback adapter is a text-only front end to the VirtIO serial RPC."""
from pathlib import Path
import json
import os
import socket
import sys
import threading
from urllib import request,error
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from veraos.virtio_model import VirtioRPC,find_port,open_loopback_compat,MODEL

@pytest.mark.skipif(os.name=="nt",reason="Windows socket handles are not POSIX file descriptors")
def test_fd_frames_have_exact_identity_and_malformed_reply_fails():
    host,guest=socket.socketpair()
    rpc=VirtioRPC(guest.fileno())
    observed=[]
    def serve():
        buf=b""
        while b"\n" not in buf:
            buf+=host.recv(4096)
        raw,extra=buf.split(b"\n",1)
        obj=json.loads(raw)
        observed.append(obj)
        host.sendall(json.dumps({"id":obj["id"],"ok":True,"models":[MODEL]}).encode()+b"\n")
    t=threading.Thread(target=serve,daemon=True);t.start()
    try:
        reply=rpc.call({"op":"models","id":"m1"},timeout=3)
        assert reply["models"]==[MODEL]
        assert observed==[{"op":"models","id":"m1"}]
        with pytest.raises(ValueError):
            rpc.call({"op":"models","id":"x"*500},timeout=2)
    finally:
        t.join(2);host.close();guest.close()

def test_guest_compat_models_and_chat_without_network_egress():
    class Mock:
        calls=[]
        def call(self,obj,**kwargs):
            self.calls.append(obj)
            if obj["op"]=="models":
                return {"models":[MODEL]}
            return {"text":"qwen-local-test"}
    mock=Mock()
    server=open_loopback_compat(mock,port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    addr=f"http://127.0.0.1:{server.server_port}"
    try:
        with request.urlopen(addr+"/v1/models",timeout=2) as x:
            assert json.load(x)["data"]==[{"id":MODEL}]
        body=json.dumps({"model":MODEL,"messages":[{"role":"user","content":"respond"}]}).encode()
        with request.urlopen(request.Request(addr+"/v1/chat/completions",body,headers={"Content-Type":"application/json"}),timeout=2) as x:
            assert json.load(x)["choices"][0]["message"]["content"]=="qwen-local-test"
        assert [x["op"] for x in mock.calls]==["models","chat"]
        for payload in ({"model":"wrong","messages":[]},
                        {"model":MODEL,"messages":[],"tools":[{"name":"exec"}]}):
            with pytest.raises(error.HTTPError) as exc:
                request.urlopen(request.Request(addr+"/v1/chat/completions",
                    json.dumps(payload).encode(),headers={"Content-Type":"application/json"}),timeout=2)
            assert exc.value.code==400
        assert len(mock.calls)==2
    finally:
        server.shutdown();server.server_close();thread.join(2)

def test_nonpresent_port_fails_closed(tmp_path):
    (tmp_path/"sys"/"vport0p1").mkdir(parents=True)
    (tmp_path/"sys"/"vport0p1"/"name").write_text("other.serial.port")
    with pytest.raises(RuntimeError):
        find_port(tmp_path/"sys",tmp_path/"dev")
