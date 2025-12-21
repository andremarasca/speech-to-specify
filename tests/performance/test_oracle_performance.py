"""Performance tests for oracle button rendering.

Per tasks.md T055 for 007-contextual-oracle-feedback.

Validates SC-001: Oracle button rendering < 200ms.
"""

import pytest
import time
import tempfile
from pathlib import Path

from src.services.oracle.manager import OracleManager
from src.services.telegram.keyboards import build_oracle_keyboard


class TestOracleButtonPerformance:
    """Performance tests for oracle button rendering."""
    
    @pytest.fixture
    def temp_oracles_dir(self):
        """Create temp directory with sample oracles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            oracles_path = Path(tmpdir)
            
            # Create 5 sample oracles (typical usage)
            for i in range(5):
                oracle_file = oracles_path / f"oracle_{i}.md"
                oracle_file.write_text(
                    f"# Oracle {i}\n\nYou are oracle {i}.\n\n{{{{CONTEXT}}}}\n\nProvide feedback.",
                    encoding="utf-8"
                )
            
            yield oracles_path
    
    def test_oracle_list_performance_cold(self, temp_oracles_dir):
        """SC-001: Initial oracle loading should be fast.
        
        Cold cache loading (first call) should complete within 200ms.
        """
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=10)
        
        start = time.perf_counter()
        oracles = manager.list_oracles()
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert len(oracles) == 5
        assert elapsed_ms < 200, f"Cold cache took {elapsed_ms:.1f}ms (limit: 200ms)"
    
    def test_oracle_list_performance_warm(self, temp_oracles_dir):
        """SC-001: Cached oracle listing should be very fast.
        
        Warm cache (subsequent calls) should be nearly instant (<10ms).
        """
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=10)
        
        # Warm up cache
        manager.list_oracles()
        
        # Measure cached access
        start = time.perf_counter()
        oracles = manager.list_oracles()
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert len(oracles) == 5
        assert elapsed_ms < 10, f"Warm cache took {elapsed_ms:.1f}ms (limit: 10ms)"
    
    def test_keyboard_building_performance(self, temp_oracles_dir):
        """SC-001: Building keyboard from oracles should be fast.
        
        Building InlineKeyboard from oracle list should be under 50ms.
        """
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=10)
        oracles = manager.list_oracles()
        
        start = time.perf_counter()
        keyboard = build_oracle_keyboard(oracles, simplified=False, include_llm_history=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert keyboard is not None
        assert elapsed_ms < 50, f"Keyboard build took {elapsed_ms:.1f}ms (limit: 50ms)"
    
    def test_full_flow_performance(self, temp_oracles_dir):
        """SC-001: Complete oracle button rendering flow under 200ms.
        
        Full flow: load oracles + build keyboard should be under 200ms.
        """
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=10)
        
        start = time.perf_counter()
        oracles = manager.list_oracles()
        keyboard = build_oracle_keyboard(oracles, simplified=False, include_llm_history=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert keyboard is not None
        assert elapsed_ms < 200, f"Full flow took {elapsed_ms:.1f}ms (limit: 200ms)"
    
    def test_performance_with_many_oracles(self, temp_oracles_dir):
        """SC-001: Performance holds with more oracles.
        
        Even with 20 oracles, should stay under 200ms.
        """
        # Add more oracles
        for i in range(5, 20):
            oracle_file = temp_oracles_dir / f"oracle_{i}.md"
            oracle_file.write_text(
                f"# Oracle {i}\n\nYou are oracle {i}.\n\n{{{{CONTEXT}}}}\n\nProvide feedback.",
                encoding="utf-8"
            )
        
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=10)
        
        start = time.perf_counter()
        oracles = manager.list_oracles()
        keyboard = build_oracle_keyboard(oracles, simplified=False, include_llm_history=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert len(oracles) == 20
        assert keyboard is not None
        assert elapsed_ms < 200, f"20 oracles took {elapsed_ms:.1f}ms (limit: 200ms)"
