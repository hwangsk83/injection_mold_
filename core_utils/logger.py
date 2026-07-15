# -*- coding: utf-8 -*-
"""
core_utils.logger -- Unified Structured Logging
================================================
Replaces print()-based logging scattered across 108+ files with
a structured, timestamped logging system.

Usage:
    from core_utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Processing started")
    log.warning("Memory usage high: %d MB", mem_mb)
    log.phase("Phase 7: Assembly Manager")

Features:
  - Timestamped, module-named loggers
  - Phase tracking with automatic timing
  - @log_timing decorator for function profiling
  - Memory usage logging hooks
  - Audit-level message constants
"""

import logging
import os
import sys
import time
import functools
from pathlib import Path
from datetime import datetime
from typing import Optional

# -- Global config --
_LOG_FILE: Optional[Path] = None
_LOG_LEVEL: int = logging.INFO
_LOGGERS: dict = {}


def configure(log_file: Optional[str] = None, level: int = logging.INFO):
    """
    Global logger configuration. Call once at app startup.

    Parameters
    ----------
    log_file : path to log file (optional), if None logs to stdout only
    level : logging level (INFO, DEBUG, WARNING, etc.)
    """
    global _LOG_FILE, _LOG_LEVEL
    _LOG_LEVEL = level

    if log_file:
        _LOG_FILE = Path(log_file)
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Clear cached loggers so they pick up new config
    _LOGGERS.clear()


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a named logger. Reuses existing instances.

    Usage:
        log = get_logger(__name__)
        log.info("Message")

    The logger prepends [ModuleName] and timestamps automatically.
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(f"simple-injection-mold-sim.{name}")
    logger.setLevel(_LOG_LEVEL)
    logger.propagate = False

    # Avoid adding duplicate handlers
    if not logger.handlers:
        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(_LOG_LEVEL)
        fmt = logging.Formatter(
            "[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S"
        )
        console.setFormatter(fmt)
        logger.addHandler(console)

        # File handler if configured
        if _LOG_FILE:
            file_handler = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)

    _LOGGERS[name] = logger
    return logger


# -- Phase tracking --
_PHASE_START_TIMES: dict = {}


def log_phase(logger, phase_name: str):
    """
    Log the start of a processing phase with automatic timing.
    Call log_phase_end() to print elapsed time.
    """
    _PHASE_START_TIMES[phase_name] = time.perf_counter()
    logger.info("=" * 60)
    logger.info("PHASE START: %s", phase_name)
    logger.info("=" * 60)


def log_phase_end(logger, phase_name: str, success: bool = True):
    """Log the end of a phase with elapsed time."""
    start = _PHASE_START_TIMES.pop(phase_name, None)
    elapsed = f"{(time.perf_counter() - start) * 1000:.1f} ms" if start else "unknown"
    status = "SUCCESS" if success else "FAILED"
    logger.info("PHASE END: %s [%s] [%s]", phase_name, elapsed, status)


# -- Decorators --
def log_timing(logger=None):
    """
    Decorator that logs function execution time.

    Usage:
        @log_timing()
        def heavy_computation(): ...

        @log_timing(logger=my_logger)
        def specific_func(): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = logger or get_logger(func.__module__)
            t0 = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                dt = (time.perf_counter() - t0) * 1000
                log.debug("%s() completed in %.1f ms", func.__name__, dt)
                return result
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                log.error("%s() FAILED after %.1f ms: %s", func.__name__, dt, e)
                raise
        return wrapper
    # Support @log_timing() and @log_timing(logger=X)
    if callable(logger):
        # Called as @log_timing without parentheses
        func = logger
        return decorator(func)
    return decorator


# -- Memory logging --
def log_memory(logger, tag: str = ""):
    """Log current memory usage (Linux/Windows)."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / (1024 * 1024)
        logger.info("MEMORY [%s]: %.1f MB", tag, mem_mb)
    except ImportError:
        pass  # psutil not installed, skip silently


# -- Audit-level constants (for system_auditor compatibility) --
AUDIT_PASS = "PASS"
AUDIT_FAIL = "FAIL"
AUDIT_SKIP = "SKIP"
AUDIT_SELF_HEAL = "SELF-HEAL"


def audit_result(logger, check_id: int, result: str, detail: str = ""):
    """Log an audit check result with structured format."""
    level = logging.INFO if result == AUDIT_PASS else logging.WARNING
    logger.log(level, "[AUDIT Check %d] %s: %s", check_id, result, detail)