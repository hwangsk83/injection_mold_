# -*- coding: utf-8 -*-
"""
in_memory_profiler.py -- In-Memory Leak Detection & Performance Profiler
==========================================================================
Phase 23: mesh_utils.py의 merge_stls_in_memory()를 10회 반복 실행하는
스트레스 테스트를 통해 메모리 누수 및 디스크 I/O 오버헤드를 검증.

검증 로직:
  1. 대상: core_utils.mesh_utils.merge_stls_in_memory()
  2. psutil.Process().memory_info() 로 반복 전/중/후 RAM 추적
  3. 10회 반복 실행 후 gc.collect() 강제 호출
  4. 최종 RAM vs 초기 RAM 비교 → Leak Δ = 0MB 검증
  5. psutil.disk_io_counters() 로 디스크 쓰기 = 0 byte 검증

Usage:
    python in_memory_profiler.py [--stl PATH] [--iterations N]
"""
import os
import sys
import gc
import time
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional


# ============================================================================
# 메모리 / 디스크 I/O 측정 유틸리티
# ============================================================================

def get_memory_usage_mb() -> float:
    """현재 프로세스의 RSS 메모리 사용량 (MB)."""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def get_disk_io_counters() -> Optional[Dict[str, int]]:
    """시스템 디스크 I/O 카운터 반환."""
    try:
        import psutil
        counters = psutil.disk_io_counters()
        if counters:
            return {
                "read_count": counters.read_count,
                "write_count": counters.write_count,
                "read_bytes": counters.read_bytes,
                "write_bytes": counters.write_bytes,
            }
    except (ImportError, AttributeError):
        pass
    return None


def delta_io(before: Optional[Dict[str, int]], after: Optional[Dict[str, int]]) -> Dict[str, int]:
    """두 I/O 카운터의 차이를 계산."""
    if before is None or after is None:
        return {"write_count": 0, "write_bytes": 0, "read_count": 0, "read_bytes": 0}
    return {
        "write_count": after["write_count"] - before["write_count"],
        "write_bytes": after["write_bytes"] - before["write_bytes"],
        "read_count": after["read_count"] - before["read_count"],
        "read_bytes": after["read_bytes"] - before["read_bytes"],
    }


# ============================================================================
# 스트레스 테스트
# ============================================================================

def run_stress_test(
    stl_path: Path,
    iterations: int = 10,
    debug: bool = False
) -> Dict[str, any]:
    """
    merge_stls_in_memory() 10회 반복 스트레스 테스트.

    Parameters
    ----------
    stl_path : 테스트할 STL 파일 경로
    iterations : 반복 횟수
    debug : 상세 출력 여부

    Returns
    -------
    dict: {
        "iterations": int,
        "initial_ram_mb": float,
        "peak_ram_mb": float,
        "final_ram_mb": float,
        "leak_mb": float,
        "ram_history": [...],
        "total_disk_writes": int,
        "total_disk_write_bytes": int,
        "result": "PASS" / "FAIL",
        ...
    }
    """
    print("=" * 70)
    print("  IN-MEMORY PROFILER -- Leak Detection & I/O Monitor")
    print("=" * 70)

    if not stl_path.exists():
        print(f"  [ERROR] STL not found: {stl_path}")
        return {"result": "ERROR", "error": f"STL not found: {stl_path}"}

    # 스트레스 테스트 전 메모리/디스크 스냅샷
    initial_ram = get_memory_usage_mb()
    initial_io = get_disk_io_counters()

    print(f"\n[SETUP] Target STL: {stl_path.name}")
    print(f"  Initial RAM: {initial_ram:.2f} MB")
    if initial_io:
        print(f"  Initial disk write_count: {initial_io['write_count']}, write_bytes: {initial_io['write_bytes']}")

    # merge_stls_in_memory 임포트
    try:
        from core_utils.mesh_utils import merge_stls_in_memory, estimate_memory_footprint
    except ImportError as e:
        print(f"  [ERROR] Cannot import mesh_utils: {e}")
        return {"result": "ERROR", "error": str(e)}

    # --- 반복 스트레스 테스트 ---
    ram_history = []
    peak_ram = initial_ram
    stl_paths = [str(stl_path)]

    print(f"\n[STRESS TEST] Running {iterations} iterations...")
    print(f"  {'Iter':<6} {'RAM_before':>10} {'RAM_after':>10} {'Delta':>10} {'Verts':>8} {'Faces':>8} {'Mem(MB)':>10}")
    print(f"  {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*10}")

    for i in range(1, iterations + 1):
        ram_before = get_memory_usage_mb()

        # In-Memory 연산 실행
        mesh = merge_stls_in_memory(stl_paths, debug=False)

        ram_after = get_memory_usage_mb()
        delta_ram = ram_after - ram_before
        peak_ram = max(peak_ram, ram_after)

        n_verts = len(mesh.vertices) if mesh else 0
        n_faces = len(mesh.faces) if mesh else 0
        mem_est = estimate_memory_footprint(mesh) / (1024 * 1024) if mesh else 0

        ram_history.append({
            "iteration": i,
            "ram_before_mb": round(ram_before, 3),
            "ram_after_mb": round(ram_after, 3),
            "delta_mb": round(delta_ram, 3),
        })

        print(f"  {i:<6} {ram_before:>10.2f} {ram_after:>10.2f} {delta_ram:>+10.3f} {n_verts:>8} {n_faces:>8} {mem_est:>10.3f}")

        # mesh 참조 해제 (GC가 수집할 수 있도록)
        del mesh

    # --- GC 및 최종 측정 ---
    print(f"\n[GC] Forcing garbage collection...")
    gc.collect()

    # GC 후 잠시 대기 (OS 메모리 반환)
    time.sleep(0.5)

    final_ram = get_memory_usage_mb()
    final_io = get_disk_io_counters()
    leak_mb = final_ram - initial_ram

    # I/O delta 계산
    if initial_io and final_io:
        io_delta = delta_io(initial_io, final_io)
    else:
        io_delta = {"write_count": 0, "write_bytes": 0, "read_count": 0, "read_bytes": 0}

    # --- 결과 평가 ---
    print(f"\n[RESULTS]")
    print(f"  Initial RAM:    {initial_ram:.2f} MB")
    print(f"  Peak RAM:       {peak_ram:.2f} MB")
    print(f"  Final RAM:      {final_ram:.2f} MB")
    print(f"  Leak (Δ):       {leak_mb:+.3f} MB")
    print(f"  Disk writes:    {io_delta['write_count']} ops, {io_delta['write_bytes']} bytes")

    # 판정
    leak_ok = abs(leak_mb) < 1.0  # 1MB 미만은 허용 (OS 페이지 캐시 등)
    disk_ok = io_delta["write_bytes"] == 0

    if leak_ok and disk_ok:
        print(f"\n  [PASS] Zero Memory Leak + Zero Disk Write Overhead")
        result_status = "PASS"
    elif leak_ok:
        print(f"\n  [WARN] Memory OK but {io_delta['write_bytes']} bytes written to disk")
        result_status = "PARTIAL"
    elif disk_ok:
        print(f"\n  [WARN] Disk OK but memory leak = {leak_mb:.3f} MB")
        result_status = "PARTIAL"
    else:
        print(f"\n  [FAIL] Memory leak = {leak_mb:.3f} MB, Disk writes = {io_delta['write_bytes']} bytes")
        result_status = "FAIL"

    return {
        "result": result_status,
        "iterations": iterations,
        "stl_path": str(stl_path),
        "initial_ram_mb": round(initial_ram, 3),
        "peak_ram_mb": round(peak_ram, 3),
        "final_ram_mb": round(final_ram, 3),
        "leak_mb": round(leak_mb, 3),
        "leak_ok": leak_ok,
        "ram_history": ram_history,
        "disk_writes_count": io_delta["write_count"],
        "disk_writes_bytes": io_delta["write_bytes"],
        "disk_io_ok": disk_ok,
    }


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="In-Memory Profiler — Leak Detection & I/O Monitor"
    )
    parser.add_argument(
        "--stl", type=str,
        default="validation_test/constant/triSurface/case_model.stl",
        help="STL file path for stress test"
    )
    parser.add_argument(
        "--iterations", type=int, default=10,
        help="Number of stress test iterations"
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: 3 iterations only"
    )
    args = parser.parse_args()

    workspace = Path.cwd()
    stl_path = workspace / args.stl
    iterations = 3 if args.quick else args.iterations

    # 스트레스 테스트 실행
    result = run_stress_test(stl_path, iterations=iterations, debug=False)

    # 리포트 저장
    report_path = workspace / "inmemory_profiler_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)
    print(f"\n[REPORT] Saved: {report_path}")

    # 종합 리포트 출력
    print("\n" + "=" * 70)
    print("  IN-MEMORY PROFILER -- FINAL VERDICT")
    print("=" * 70)
    print(f"  Status:      {result.get('result', 'UNKNOWN')}")
    print(f"  Iterations:  {result.get('iterations', 0)}")
    print(f"  Memory Leak: {result.get('leak_mb', 0):+.3f} MB")
    print(f"  Disk Writes: {result.get('disk_writes_bytes', 0)} bytes")
    print("=" * 70)

    return 0 if result.get("result") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())