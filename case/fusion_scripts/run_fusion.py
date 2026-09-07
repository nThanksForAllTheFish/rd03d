#!/usr/bin/env python3
"""Send a Fusion API script to the local Fusion MCP server, or grab a screenshot.

Usage:
  run_fusion.py script <file.py> [--read-only]
  run_fusion.py screenshot <out.png> [direction]
"""
import base64
import json
import sys
import urllib.request

URL = "http://127.0.0.1:27182/mcp"


def rpc(session, payload):
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if session:
        headers["MCP-Session-Id"] = session
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r:
        sid = r.headers.get("MCP-Session-Id", session)
        body = r.read().decode()
    return sid, (json.loads(body) if body.strip() else None)


def connect():
    sid, _ = rpc(None, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-03-26",
                                   "capabilities": {},
                                   "clientInfo": {"name": "rd03d-case-builder",
                                                  "version": "1.0"}}})
    rpc(sid, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    return sid


def call(sid, name, args):
    _, resp = rpc(sid, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": name, "arguments": args}})
    if resp is None:
        raise SystemExit("empty MCP response")
    if "error" in resp:
        raise SystemExit(f"MCP error: {resp['error']}")
    return resp["result"].get("content", [])


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    mode = sys.argv[1]
    sid = connect()

    if mode == "script":
        src = open(sys.argv[2]).read()
        obj = {"script": src}
        if "--read-only" in sys.argv:
            obj["readOnly"] = True
        content = call(sid, "fusion_mcp_execute",
                       {"featureType": "script", "object": obj})
        ok = True
        for c in content:
            if c.get("type") != "text":
                continue
            try:
                d = json.loads(c["text"])
                if not isinstance(d, dict):
                    print(c["text"])
                    continue
                print(d.get("message", c["text"]))
                if d.get("success") is False or "error" in d:
                    ok = False
            except json.JSONDecodeError:
                print(c["text"])
        sys.exit(0 if ok else 1)

    if mode == "screenshot":
        out = sys.argv[2]
        args = {"queryType": "screenshot", "width": 1200, "height": 900}
        if len(sys.argv) > 3 and not sys.argv[3].startswith("--"):
            args["direction"] = sys.argv[3]
        content = call(sid, "fusion_mcp_read", args)
        for c in content:
            if c.get("type") == "image" and c.get("data"):
                data = base64.b64decode(c["data"])
                open(out, "wb").write(data)
                print("saved", out)
                return
            if c.get("type") == "text":
                try:
                    d = json.loads(c["text"])
                    img = d.get("imageData") or d.get("data")
                    if img:
                        data = base64.b64decode(img)
                        open(out, "wb").write(data)
                        print("saved", out)
                        return
                    print(c["text"][:400])
                except json.JSONDecodeError:
                    print(c["text"][:400])
        raise SystemExit("no image in response")

    raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
