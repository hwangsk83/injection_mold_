# -*- coding: utf-8 -*-
"""
core_utils.portable_env_injector -- Zero-Installation Portable Ecosystem
=========================================================================
동적 환경 변수 주입기: 실행 파일 기준의 현재 절대 경로를 역추적하여
embedded_runtime/bluecfd_core 및 embedded_runtime/mpi 경로를 빌드한 후,
subprocess 실행 시 env 파라미터에 동적으로 삽입.

Usage:
    from core_utils.portable_env_injector import (
        get_runtime_root,
        build_embedded_paths,
        inject_env,
        get_mpiexec_path,
    )

    env = inject_env()  # PATH + OpenFOAM env injected
    subprocess.run(["injectionFoam"], env=env)
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# 캐시: 프로젝트 루트를 한 번만 계산
# ---------------------------------------------------------------------------
_RUNTIME_ROOT: Optional[Path] = None


def get_runtime_root() -> Path:
    """
    현재 파일(__file__)의 절대 경로를 기준으로 프로젝트 루트를 역추적.

    Returns
    -------
    Path : 프로젝트 루트 디렉토리
    """
    global _RUNTIME_ROOT
    if _RUNTIME_ROOT is not None:
        return _RUNTIME_ROOT

    # 우선순위: 환경변수 > __file__ 기반 > cwd
    env_root = os.environ.get("IMF_RUNTIME_ROOT")
    if env_root:
        candidate = Path(env_root)
        if candidate.exists():
            _RUNTIME_ROOT = candidate
            return _RUNTIME_ROOT

    # __file__ 기반 추론: core_utils/portable_env_injector.py -> core_utils/ -> root
    try:
        this_file = Path(__file__).resolve()
        # core_utils/portable_env_injector.py
        core_utils_dir = this_file.parent          # core_utils/
        runtime_root = core_utils_dir.parent       # 프로젝트 루트
        _RUNTIME_ROOT = runtime_root
    except (NameError, AttributeError):
        # __file__이 정의되지 않은 인터랙티브 환경
        _RUNTIME_ROOT = Path.cwd()

    return _RUNTIME_ROOT


def build_embedded_paths(runtime_root: Optional[Path] = None) -> Dict[str, Path]:
    """
    임베디드 런타임 내 blueCFD 및 MPI 바이너리 경로를 빌드.

    Parameters
    ----------
    runtime_root : 프로젝트 루트 (None이면 자동 감지)

    Returns
    -------
    dict: {
        "bluecfd_bin": Path,       # blueCFD-Core 실행 파일 디렉토리
        "bluecfd_bash": Path,      # bash.exe
        "mpi_bin": Path,           # MPI 실행 파일 디렉토리
        "mpiexec": Path,           # mpiexec.exe
    }
    """
    if runtime_root is None:
        runtime_root = get_runtime_root()

    # 임베디드 런타임 기본 구조
    embedded = runtime_root / "embedded_runtime"

    bluecfd_bin = embedded / "bluecfd_core" / "bin"
    bluecfd_bash = embedded / "bluecfd_core" / "msys64" / "usr" / "bin" / "bash.exe"
    mpi_bin = embedded / "mpi" / "bin"
    mpiexec = mpi_bin / "mpiexec.exe"

    return {
        "bluecfd_bin": bluecfd_bin,
        "bluecfd_bash": bluecfd_bash,
        "mpi_bin": mpi_bin,
        "mpiexec": mpiexec,
    }


def get_mpiexec_path() -> Path:
    """임베디드 MPI의 mpiexec.exe 절대 경로를 반환."""
    paths = build_embedded_paths()
    return paths["mpiexec"]


def get_bash_path() -> Path:
    """임베디드 blueCFD의 bash.exe 절대 경로를 반환."""
    paths = build_embedded_paths()
    return paths["bluecfd_bash"]


def inject_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    현재 환경에 blueCFD 및 MPI 바이너리 경로를 동적으로 주입.

    Parameters
    ----------
    base_env : 기존 환경 dict (None이면 os.environ 복사본 사용)

    Returns
    -------
    dict : PATH, WM_PROJECT 등이 주입된 새 환경 변수 dict
    """
    import copy

    if base_env is None:
        env = copy.deepcopy(dict(os.environ))
    else:
        env = copy.deepcopy(base_env)

    paths = build_embedded_paths()
    runtime_root = get_runtime_root()

    # --- PATH 주입 ---
    bluecfd_bin_str = str(paths["bluecfd_bin"])
    mpi_bin_str = str(paths["mpi_bin"])

    existing_path = env.get("PATH", "")
    path_parts = [p for p in existing_path.split(os.pathsep) if p]

    # 중복 방지: blueCFD, MPI 경로가 없으면 앞쪽에 삽입
    injected = []
    for inject_path in [mpi_bin_str, bluecfd_bin_str]:
        if inject_path not in path_parts:
            injected.append(inject_path)

    if injected:
        env["PATH"] = os.pathsep.join(injected + path_parts)

    # --- OpenFOAM 환경 변수 ---
    env.setdefault("WM_PROJECT", "OpenFOAM")
    env.setdefault("WM_PROJECT_VERSION", "12")
    env.setdefault("WM_OPTIONS", "windowsMingw64DPInt32Opt")
    env.setdefault("FOAM_API", "2404")

    # OpenFOAM 등록 경로 (embedded_runtime 기준)
    env.setdefault("WM_PROJECT_DIR", str(paths["bluecfd_bin"].parent))
    env.setdefault("FOAM_USER_APPBIN", str(runtime_root))

    # --- MPI 환경 ---
    env.setdefault("I_MPI_ROOT", str(paths["mpi_bin"].parent))
    env.setdefault("OMPI_MCA_rmaps_base_oversubscribe", "1")

    # MSYS2 런타임 환경
    msys_root = paths["bluecfd_bash"].parent.parent.parent  # msys64/
    env.setdefault("MSYS2_PATH_TYPE", "inherit")

    # --- IMF 런타임 마커 ---
    env["IMF_RUNTIME_ROOT"] = str(runtime_root)
    env["IMF_EMBEDDED_BLUECFD"] = str(paths["bluecfd_bin"])
    env["IMF_EMBEDDED_MPI"] = str(paths["mpi_bin"])

    return env


def validate_embedded_paths() -> Tuple[bool, list]:
    """
    모든 임베디드 경로의 유효성을 검증.

    Returns
    -------
    (is_valid, missing_paths)
    """
    paths = build_embedded_paths()
    missing = []

    for name, path_obj in paths.items():
        if not path_obj.exists():
            missing.append(f"{name}: {path_obj}")

    return len(missing) == 0, missing


def get_openfoam_solver_path(solver_name: str) -> Optional[Path]:
    """
    임베디드 blueCFD에서 OpenFOAM 솔버 실행 파일 경로를 찾는다.

    Parameters
    ----------
    solver_name : e.g., "injectionFoam", "blockMesh", "decomposePar"

    Returns
    -------
    Path or None
    """
    paths = build_embedded_paths()
    solver_path = paths["bluecfd_bin"] / f"{solver_name}.exe"
    if solver_path.exists():
        return solver_path
    # .exe 없이도 존재할 수 있음
    solver_path_noext = paths["bluecfd_bin"] / solver_name
    if solver_path_noext.exists():
        return solver_path_noext
    return None