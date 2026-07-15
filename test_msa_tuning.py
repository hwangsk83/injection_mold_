# -*- coding: utf-8 -*-
"""
test_msa_tuning.py - Comprehensive MSA & Self-Learning Validation Test

Runs non-blocking API Gateway test clients, triggers cognitive Bayesian tuning,
and validates standard V&V tolerances below 0.1% error.
"""
import os
import json
import time
from fastapi.testclient import TestClient
from fastapi_celery_gateway import app
from cognitive_tuning_engine import run_bayesian_optimization

def test_api_gateway_nonblocking():
    print("\n--- [TEST] 1. Asynchronous API Gateway Validation ---")
    client = TestClient(app)
    
    # Submit job
    payload = {"case_name": "Grid_10M_Coarse", "parameters": {"cycles": 5}}
    resp_submit = client.post("/api/v1/solve", json=payload)
    assert resp_submit.status_code == 200
    data_submit = resp_submit.json()
    task_id = data_submit["task_id"]
    print(f"[SUCCESS] Submitted task asynchronously. Task ID: {task_id}")
    
    # Poll status
    time.sleep(0.5)
    resp_status = client.get(f"/api/v1/status/{task_id}")
    assert resp_status.status_code == 200
    data_status = resp_status.json()
    print(f"[SUCCESS] Polled status. State: {data_status['status']}, Progress: {data_status['progress']}%")
    
    # Wait for completion
    print("Waiting for worker simulation to complete...")
    for _ in range(12):
        time.sleep(0.4)
        resp_status = client.get(f"/api/v1/status/{task_id}")
        data_status = resp_status.json()
        if data_status["status"] == "SUCCESS":
            break
            
    assert data_status["status"] == "SUCCESS"
    assert data_status["progress"] == 100
    print(f"[SUCCESS] Task finished. Result: {data_status['result']}")
    return True

def test_cognitive_tuning_convergence():
    print("\n--- [TEST] 2. Cognitive Self-Tuning Engine Validation ---")
    tuning_results = run_bayesian_optimization(max_iter=10)
    
    # Verify convergence rate
    best_err = tuning_results["best_error_pct"]
    print(f"Calibrated Optimal Parameters: {tuning_results['best_params']}")
    print(f"Final error reached: {best_err:.6f}%")
    
    assert best_err < 0.1
    print("[SUCCESS] Parameter optimization achieved exact error convergence < 0.1%.")
    return tuning_results

def run_all_tests():
    print("=" * 65)
    print("       PROJECT TITAN MSA & SELF-LEARNING INTEGRATION TEST")
    print("=" * 65)
    
    # 1. API gateway test
    gateway_ok = test_api_gateway_nonblocking()
    
    # 2. Tuning engine test
    tuning_data = test_cognitive_tuning_convergence()
    
    print("\n" + "=" * 65)
    print("   INTEGRATION STATUS: 100% COMPLETE & VERIFIED")
    print("=" * 65)
    
    # Write integration report findings
    report_findings = {
        "gateway_test_passed": gateway_ok,
        "tuning_test_passed": True,
        "calibrated_coefficients": tuning_data["best_params"],
        "final_error_pct": tuning_data["best_error_pct"]
    }
    
    return report_findings

if __name__ == "__main__":
    run_all_tests()
