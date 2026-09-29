"""Local development HTTP API. Bind to localhost; no authentication or remote deployment support."""
from __future__ import annotations
import csv,io,json,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlparse

from .service import AnalysisService


def handler_for(service):
    class Handler(BaseHTTPRequestHandler):
        def _send(self,status,payload,content_type="application/json"):
            body=payload if isinstance(payload,bytes) else json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(body))); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Headers","Content-Type,X-Filename,X-Source-Dataset"); self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS"); self.end_headers(); self.wfile.write(body)
        def do_OPTIONS(self): self._send(204,b"")
        def do_GET(self):
            path=urlparse(self.path).path
            if path=="/api/health": return self._send(200,{"status":"ok","mode":service.mode,"engine4":"READY" if service.mode=="REAL" else "MOCK","subpipe":"PENDING"})
            if path=="/api/reviews": return self._send(200,service._read_reviews())
            if path=="/api/export":
                reviews=service._read_reviews(); fmt=parse_qs(urlparse(self.path).query).get("format",["json"])[0]
                if fmt=="csv":
                    output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=["detection_id","review_status","note","updated_at"]); writer.writeheader()
                    for key,value in reviews.items(): writer.writerow({"detection_id":key,"review_status":value.get("status"),"note":value.get("note"),"updated_at":value.get("updated_at")})
                    return self._send(200,output.getvalue().encode(),"text/csv; charset=utf-8")
                return self._send(200,{"human_reviews":reviews,"mode":service.mode})
            return self._send(404,{"error":"not found"})
        def do_POST(self):
            path=urlparse(self.path).path
            try:
                length=int(self.headers.get("Content-Length","0"))
                if path=="/api/analyze":
                    if length<=0 or length>service.config["max_upload_bytes"]: return self._send(413,{"error":"image body is empty or exceeds upload limit"})
                    body=self.rfile.read(length); filename=self.headers.get("X-Filename","upload"); source=self.headers.get("X-Source-Dataset","ALL")
                    return self._send(200,service.analyze_bytes(body,filename=filename,source_dataset=source))
                if path=="/api/review":
                    if length<=0 or length>10000: return self._send(413,{"error":"invalid review request size"})
                    data=json.loads(self.rfile.read(length))
                    if not isinstance(data,dict): return self._send(400,{"error":"review body must be a JSON object"})
                    return self._send(200,service.save_review(data.get("detection_id",""),data.get("action",""),data.get("note","")))
                return self._send(404,{"error":"not found"})
            except (ValueError,json.JSONDecodeError) as exc: return self._send(400,{"error":str(exc)})
            except Exception as exc: return self._send(500,{"error":str(exc)})
        def log_message(self,format,*args): pass
    return Handler


def main():
    service=AnalysisService(review_store=os.environ.get("SIH_REVIEW_STORE","data/engine8/reviews.json"))
    host=os.environ.get("SIH_API_HOST","127.0.0.1"); port=int(os.environ.get("SIH_API_PORT","8000"))
    server=ThreadingHTTPServer((host,port),handler_for(service)); print(f"Engine 8 API listening at http://{host}:{port} ({service.mode}; Engine 4 and SubPipe pending)")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=="__main__": main()
