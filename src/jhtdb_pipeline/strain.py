"""Compatibility API; block-specific implementation lives in block_statistics."""
from block_statistics.strain import (
    STRAIN_CACHE_VERSION, ensure_strain_cache, _accumulate, _cache_is_current, _build_cache,
)

__all__ = ["STRAIN_CACHE_VERSION", "ensure_strain_cache"]
