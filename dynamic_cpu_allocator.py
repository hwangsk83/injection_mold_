# -*- coding: utf-8 -*-
"""
dynamic_cpu_allocator.py -- Hardware-Aware Parallel Decomposition Optimizer
============================================================================
Phase 23: 타 PC의 CPU 코어 수를 자동 감지하여 OpenFOAM decomposeParDict의
numberOfSubdomains 및 hierarchicalCoeffs n 값을 동적으로 최적화.

검증 로직:
  1. os.cpu_count() / psutil.cpu_count() 로 물리/논리 코어 감지
  2. 안전 가용 코어 = int(물리_코어 * 0.8), 최소 1
  3. decomposeParDict 파일을 런타임에 동적으로 오버라이드
  4. 백업 생성 및 복원 기능 제공

Usage:
    python dynamic_cpu_allocator.py [--case CASE_DIR] [--restore]
"""
import os
import sys
import math
import shutil
import argparse
from pathlib import Path
from typing import Tuple, Dict, Optional


# ============================================================================
# CPU 코어 감지
# ============================================================================

def detect_cpu_cores() -> Dict[str, int]:
    """
    현재 시스템의 CPU 코어 정보를 반환.

    Returns
    -------
    dict: {
        "logical": int,       # 논리 코어 (하이퍼스레딩 포함)
        "physical": int,      # 물리 코어
        "safe_cores": int,    # 안전 가용 코어 (80%)
    }
    """
    logical = os.cpu_count() or 1

    # 물리 코어 감지 시도
    physical = logical
    try:
        import psutil
        phys = psutil.cpu_count(logical=False)
        if phys and phys > 0:
            physical = phys
    except ImportError:
        # psutil 없는 경우: 일반적으로 하이퍼스레딩=2 가정
        if logical >= 4:
            physical = logical // 2
        else:
            physical = logical

    # 안전 가용 코어: 물리 코어의 80% (시스템 여유분 20% 확보)
    safe_cores = max(1, int(physical * 0.8))

    return {
        "logical": logical,
        "physical": physical,
        "safe_cores": safe_cores,
    }


# ============================================================================
# decomposeParDict n-factor 분해
# ============================================================================

def factorize_n(n: int) -> Tuple[int, int, int]:
    """
    numberOfSubdomains n을 (nx, ny, nz)로 분해.
    OpenFOAM의 hierarchical 분해에 최적화된 인수분해.

    Parameters
    ----------
    n : 총 파티션 수

    Returns
    -------
    (nx, ny, nz) 튜플
    """
    if n <= 1:
        return (1, 1, 1)

    # 우선순위: x방향(유동 방향) 우선 분해
    # 세제곱근 근처에서 시작
    cbrt = int(round(n ** (1.0 / 3.0)))

    best = (n, 1, 1)
    best_cost = float("inf")

    for nx in range(max(1, cbrt - 2), min(n, cbrt + 3)):
        if n % nx == 0:
            remaining = n // nx
            for ny in range(1, remaining + 1):
                if remaining % ny == 0:
                    nz = remaining // ny
                    # 비용 함수: 불균형 최소화 (nx, ny, nz 가 최대한 균등)
                    vals = [nx, ny, nz]
                    cost = max(vals) - min(vals) + (1.0 / (nx * ny * nz + 1))
                    if cost < best_cost:
                        best_cost = cost
                        best = (nx, ny, nz)

    return best


# ============================================================================
# decomposeParDict 오버라이드
# ============================================================================

DECOMPOSE_PAR_DICT_TEMPLATE = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      decomposeParDict;
}}
numberOfSubdomains {n_subdomains};

method          hierarchical;

hierarchicalCoeffs
{{
    n               ({nx} {ny} {nz});
    delta           0.001;
    order           xyz;
}}
"""


def generate_decompose_par_dict(
    n_subdomains: int,
    nx: int, ny: int, nz: int,
) -> str:
    """decomposeParDict 파일 내용을 생성."""
    return DECOMPOSE_PAR_DICT_TEMPLATE.format(
        n_subdomains=n_subdomains, nx=nx, ny=ny, nz=nz
    )


def apply_decompose_par_dict(
    case_dir: Path,
    n_subdomains: int,
    nx: int, ny: int, nz: int,
    dry_run: bool = False
) -> bool:
    """
    decomposeParDict 파일을 동적으로 오버라이드.

    Parameters
    ----------
    case_dir : 케이스 디렉토리 (system/ 포함)
    n_subdomains : numberOfSubdomains 값
    nx, ny, nz : hierarchicalCoeffs n 값
    dry_run : True이면 파일 쓰기 없이 내용만 출력

    Returns
    -------
    bool : 성공 여부
    """
    system_dir = case_dir / "system"
    target_file = system_dir / "decomposeParDict"
    backup_file = system_dir / "decomposeParDict.bak"

    if not system_dir.exists():
        print(f"  [ERROR] system/ directory not found: {system_dir}")
        return False

    content = generate_decompose_par_dict(n_subdomains, nx, ny, nz)

    if dry_run:
        print(f"  [DRY-RUN] Would write to: {target_file}")
        print(content)
        return True

    # 백업 생성 (최초 1회만)
    if target_file.exists() and not backup_file.exists():
        shutil.copy2(str(target_file), str(backup_file))
        print(f"  [BACKUP] Created: {backup_file}")

    # 오버라이드
    target_file.write_text(content, encoding="utf-8")
    print(f"  [WRITE] {target_file}")
    print(f"    numberOfSubdomains = {n_subdomains}")
    print(f"    hierarchicalCoeffs n = ({nx} {ny} {nz})")

    return True


def restore_decompose_par_dict(case_dir: Path) -> bool:
    """백업 파일로부터 decomposeParDict 복원."""
    system_dir = case_dir / "system"
    target_file = system_dir / "decomposeParDict"
    backup_file = system_dir / "decomposeParDict.bak"

    if backup_file.exists():
        shutil.copy2(str(backup_file), str(target_file))
        print(f"  [RESTORE] Restored from: {backup_file}")
        return True
    else:
        print(f"  [RESTORE] No backup found at {backup_file} — skipping.")
        return False


# ============================================================================
# Main
# ============================================================================

def auto_tune(case_dir: Path, dry_run: bool = False) -> Dict[str, any]:
    """
    전체 자동 튜닝 파이프라인.

    Returns
    -------
    dict : 튜닝 결과
    """
    print("=" * 70)
    print("  DYNAMIC CPU ALLOCATOR -- Hardware-Aware Parallel Optimizer")
    print("=" * 70)

    # 1. CPU 감지
    print("\n[STEP 1] Detecting CPU topology...")
    cores = detect_cpu_cores()
    print(f"  Logical cores:  {cores['logical']}")
    print(f"  Physical cores: {cores['physical']}")
    print(f"  Safe cores (80%): {cores['safe_cores']}")

    # 2. decomposeParDict n 분해
    n_subdomains = cores["safe_cores"]
    nx, ny, nz = factorize_n(n_subdomains)
    print(f"\n[STEP 2] Decomposition strategy:")
    print(f"  numberOfSubdomains = {n_subdomains}")
    print(f"  hierarchicalCoeffs n = ({nx} {ny} {nz})")
    print(f"  Factorization: {n_subdomains} = {nx} × {ny} × {nz}")

    # 3. 적용
    print(f"\n[STEP 3] Applying decomposeParDict...")
    success = apply_decompose_par_dict(
        case_dir, n_subdomains, nx, ny, nz, dry_run=dry_run
    )

    result = {
        **cores,
        "n_subdomains": n_subdomains,
        "n_factorization": [nx, ny, nz],
        "applied": success,
        "case_dir": str(case_dir),
    }

    if success:
        print(f"\n  [OK] decomposeParDict configured for {n_subdomains}-way parallel run")
    else:
        print(f"\n  [FAIL] Could not apply decomposeParDict")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Dynamic CPU Allocator — Auto-tune OpenFOAM parallel decomposition"
    )
    parser.add_argument(
        "--case", type=str, default="validation_test",
        help="Case directory (default: validation_test)"
    )
    parser.add_argument(
        "--restore", action="store_true",
        help="Restore decomposeParDict from backup"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Dry run: print config without writing"
    )
    parser.add_argument(
        "--detect-only", action="store_true",
        help="Only detect CPU cores, no file changes"
    )
    args = parser.parse_args()

    workspace = Path.cwd()
    case_dir = workspace / args.case

    # --detect-only
    if args.detect_only:
        cores = detect_cpu_cores()
        print("=" * 50)
        print("  CPU DETECTION ONLY")
        print("=" * 50)
        print(f"  Logical cores:  {cores['logical']}")
        print(f"  Physical cores: {cores['physical']}")
        print(f"  Safe cores (80%): {cores['safe_cores']}")
        return 0

    # --restore
    if args.restore:
        print("=" * 50)
        print("  Restoring original decomposeParDict...")
        print("=" * 50)
        ok = restore_decompose_par_dict(case_dir)
        return 0 if ok else 1

    # 자동 튜닝
    result = auto_tune(case_dir, dry_run=args.dry_run)

    # 결과 저장
    import json
    report_path = workspace / "cpu_allocator_result.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)
    print(f"\n[REPORT] Saved: {report_path}")

    return 0 if result["applied"] else 1


if __name__ == "__main__":
    sys.exit(main())