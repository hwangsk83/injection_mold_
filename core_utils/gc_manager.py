# -*- coding: utf-8 -*-
"""
core_utils.gc_manager -- Memory Management & Leak Prevention
=============================================================
Provides context manager for garbage collection around heavy operations.

Usage:
    from core_utils.gc_manager import MemoryGuard
    
    with MemoryGuard(threshold_mb=500):
        result = process_large_mesh(10_000_000_cells)
    # gc.collect() called on exit, large objects dereferenced
"""

import gc
import os
import sys
from typing import Optional


class MemoryGuard:
    """
    Context manager that triggers garbage collection before and after
    a memory-intensive operation. Optionally warns if memory exceeds threshold.
    
    Usage:
        with MemoryGuard(threshold_mb=500) as guard:
            large_result = heavy_function()
        print(f"Peak memory: {guard.peak_mb:.1f} MB")
    """
    
    def __init__(self, threshold_mb: float = 500, verbose: bool = False):
        self.threshold_mb = threshold_mb
        self.verbose = verbose
        self.peak_mb: float = 0.0
        self._start_mb: float = 0.0
    
    def __enter__(self):
        gc.collect()
        self._start_mb = self._get_memory_mb()
        if self.verbose:
            print(f"[MemoryGuard] Enter: {self._start_mb:.1f} MB")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        gc.collect()
        end_mb = self._get_memory_mb()
        self.peak_mb = max(self._start_mb, end_mb)
        if self.verbose:
            print(f"[MemoryGuard] Exit: {end_mb:.1f} MB (peak: {self.peak_mb:.1f} MB)")
        
        if self.peak_mb > self.threshold_mb:
            print(f"[MemoryGuard] WARNING: Peak memory {self.peak_mb:.1f} MB "
                  f"exceeds threshold {self.threshold_mb:.1f} MB")
        
        # Force dereference of large locals in the calling frame
        # (only if exception-free to avoid hiding errors)
        if exc_type is None:
            self._clean_locals()
        
        return False  # don't suppress exceptions
    
    @staticmethod
    def _get_memory_mb() -> float:
        """Get current process memory in MB."""
        try:
            import psutil
            return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0
    
    @staticmethod
    def _clean_locals():
        """Clear large local variables in the caller's frame."""
        frame = sys._getframe(2)  # caller's frame
        for name, value in list(frame.f_locals.items()):
            if _is_large(value):
                try:
                    frame.f_locals[name] = None
                except Exception:
                    pass


def _is_large(obj) -> bool:
    """Heuristic: is this object likely to consume significant memory?"""
    import numpy as np
    if isinstance(obj, (list, tuple, set, dict)):
        return len(obj) > 10000
    if isinstance(obj, np.ndarray):
        return obj.nbytes > 10 * 1024 * 1024  # 10 MB
    return False


def force_gc():
    """Convenience function for explicit GC."""
    gc.collect()


def memory_usage_mb() -> float:
    """Return current process memory usage in MB."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0