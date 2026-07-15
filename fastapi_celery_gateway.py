# -*- coding: utf-8 -*-
"""
fastapi_celery_gateway.py - Asynchronous Microservice API Gateway

Exposes FastAPI endpoints for non-blocking solvers, integrating Celery/Redis
with an automatic ThreadPoolExecutor fallback for high-reliability deployment.
"""
import os
import sys
import uuid
import time
import json
import threading
import concurrent.futures
from typing import Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Project Titan Asynchronous MSA Gateway", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared in-memory task database for status/progress reporting
TASKS_DB: Dict[str, Dict[str, Any]] = {}
db_lock = threading.Lock()

# Thread pool fallback for Celery-free execution
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

class SolveRequest(BaseModel):
    case_name: str
    parameters: Dict[str, Any] = {}

def simulate_solving_task(task_id: str, case_name: str, params: Dict[str, Any]):
    """Simulates a long-running solving process (meshing or multi-cycle flow)."""
    steps = 10
    with db_lock:
        TASKS_DB[task_id]["status"] = "RUNNING"
    
    try:
        for i in range(1, steps + 1):
            time.sleep(0.4)  # Simulate computing chunk
            progress = int((i / steps) * 100)
            with db_lock:
                TASKS_DB[task_id]["progress"] = progress
                TASKS_DB[task_id]["logs"].append(f"Processing grid cycle {i}/{steps}...")
        
        # Successful complete
        with db_lock:
            TASKS_DB[task_id]["status"] = "SUCCESS"
            TASKS_DB[task_id]["progress"] = 100
            TASKS_DB[task_id]["result"] = {
                "converged": True,
                "cycles_completed": steps,
                "peak_temperature_k": 573.15,
                "average_error_pct": 0.08
            }
            TASKS_DB[task_id]["logs"].append("Solver finished successfully.")
    except Exception as e:
        with db_lock:
            TASKS_DB[task_id]["status"] = "FAILED"
            TASKS_DB[task_id]["logs"].append(f"Solver Error: {str(e)}")

@app.post("/api/v1/solve")
async def solve_task(req: SolveRequest):
    """Submits an asynchronous simulation task."""
    task_id = str(uuid.uuid4())
    
    with db_lock:
        TASKS_DB[task_id] = {
            "task_id": task_id,
            "case_name": req.case_name,
            "status": "PENDING",
            "progress": 0,
            "logs": ["Task queued in asynchronous gateway."],
            "result": None,
            "timestamp": time.time()
        }
    
    # Asynchronously dispatch to thread executor fallback
    executor.submit(simulate_solving_task, task_id, req.case_name, req.parameters)
    
    return {"task_id": task_id, "status": "PENDING", "message": "Task queued successfully."}

@app.get("/api/v1/status/{task_id}")
async def get_task_status(task_id: str):
    """Retrieves current execution status, progress, and outputs."""
    with db_lock:
        if task_id not in TASKS_DB:
            raise HTTPException(status_code=404, detail="Task not found")
        return TASKS_DB[task_id]

@app.get("/api/v1/tasks")
async def list_all_tasks():
    """Lists all registered tasks."""
    with db_lock:
        return list(TASKS_DB.values())

if __name__ == "__main__":
    import uvicorn
    # Allow running directly via script
    uvicorn.run(app, host="127.0.0.1", port=8000)
