from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.options("/{full_path:path}")
@app.get("/{full_path:path}")
async def log_headers(request: Request, full_path: str):
    headers = dict(request.headers)
    print(f"\n=== Request to /{full_path} ===")
    print(f"Origin: {headers.get('origin', 'NOT SET')}")
    print(f"Host: {headers.get('host', 'NOT SET')}")
    print(f"X-Forwarded-For: {headers.get('x-forwarded-for', 'NOT SET')}")
    print(f"X-Forwarded-Host: {headers.get('x-forwarded-host', 'NOT SET')}")
    print(f"X-Original-Forwarded-For: {headers.get('x-original-forwarded-for', 'NOT SET')}")
    print(f"All headers: {headers}")
    return {"origin_received": headers.get('origin'), "host_received": headers.get('host')}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
