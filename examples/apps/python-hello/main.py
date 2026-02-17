"""
Python FastAPI — Hello World

A minimal production-ready FastAPI service with two endpoints:
  GET /       -> {"message": "Hello, World!"}
  GET /health -> {"status": "healthy"}

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8080
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Hello World",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)


@app.get("/")
def root():
    """Root endpoint returning a greeting."""
    return {"message": "Hello, World!"}


@app.get("/health")
def health():
    """Health check endpoint for readiness probes."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)
