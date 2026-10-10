"""Minimal WSGI cloud API for Mogh-e-Kamel + structured Brain memory."""
import json, os, mimetypes
from pathlib import Path
from urllib.parse import parse_qs
from brain import Brain
ROOT=Path(__file__).resolve().parent
WEB=ROOT/"web"
brain=Brain(os.getenv("BRAIN_DB_PATH","brain.db"))

def response(start_response, status, data, content_type="application/json; charset=utf-8"):
    body=data if isinstance(data,bytes) else (data.encode("utf-8") if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode("utf-8"))
    start_response(status,[("Content-Type",content_type),("Content-Length",str(len(body))),("Access-Control-Allow-Origin","*"),("Access-Control-Allow-Headers","Content-Type"),("Access-Control-Allow-Methods","GET,POST,OPTIONS")])
    return [body]

def app(environ,start_response):
    path=environ.get("PATH_INFO","/")
    method=environ.get("REQUEST_METHOD","GET")
    if method=="OPTIONS": return response(start_response,"204 No Content",b"")
    if path=="/api/health": return response(start_response,"200 OK",{"ok":True,"service":"mogh-kamel-cloud","brain":"structured-memory","stats":brain.stats()})
    if path=="/api/brain/stats": return response(start_response,"200 OK",brain.stats())
    if path=="/api/brain/entity" and method=="POST":
        try:
            n=int(environ.get("CONTENT_LENGTH") or 0)
            obj=json.loads(environ["wsgi.input"].read(n) or b"{}")
            eid=brain.register(str(obj.get("type","Entity")),str(obj["name"]),obj.get("aliases"),obj.get("data"))
            return response(start_response,"200 OK",{"id":eid,"stats":brain.stats()})
        except Exception as e: return response(start_response,"400 Bad Request",{"error":str(e)})
    if path=="/api/brain/claim" and method=="POST":
        try:
            n=int(environ.get("CONTENT_LENGTH") or 0); obj=json.loads(environ["wsgi.input"].read(n) or b"{}")
            eid=obj.get("entity_id") or brain.resolve(str(obj.get("entity_name","")))
            if not eid: return response(start_response,"400 Bad Request",{"error":"entity_id یا entity_name معتبر لازم است"})
            cid=brain.claim(eid,str(obj["text"]),obj.get("source","unknown"),obj.get("evidence"),obj.get("confidence",0.5))
            return response(start_response,"200 OK",{"claim_id":cid,"contradictions":brain.detect_contradiction(eid)})
        except Exception as e: return response(start_response,"400 Bad Request",{"error":str(e)})
    if path=="/api/brain/solve" and method=="POST":
        try:
            n=int(environ.get("CONTENT_LENGTH") or 0); obj=json.loads(environ["wsgi.input"].read(n) or b"{}")
            eid=obj.get("entity_id") or brain.resolve(str(obj.get("entity_name","")))
            if not eid: return response(start_response,"404 Not Found",{"error":"entity not found"})
            return response(start_response,"200 OK",brain.solve(eid))
        except Exception as e: return response(start_response,"400 Bad Request",{"error":str(e)})
    if path=="/" or path=="/index.html":
        index=WEB/"index.html"
        if index.exists(): return response(start_response,"200 OK",index.read_bytes(),"text/html; charset=utf-8")
        return response(start_response,"200 OK","<html lang='fa' dir='rtl'><meta charset='utf-8'><title>مغز کامل</title><h1>مغز کامل — Cloud</h1><p>API حافظه فعال است.</p><pre id='s'>در حال بررسی…</pre><script>fetch('/api/health').then(r=>r.json()).then(x=>s.textContent=JSON.stringify(x,null,2))</script></html>","text/html; charset=utf-8")
    if path.startswith("/"):
        candidate=(WEB/path.lstrip("/")).resolve()
        if WEB.resolve() in candidate.parents and candidate.is_file():
            return response(start_response,"200 OK",candidate.read_bytes(),mimetypes.guess_type(str(candidate))[0] or "application/octet-stream")
    return response(start_response,"404 Not Found",{"error":"not_found","path":path})
