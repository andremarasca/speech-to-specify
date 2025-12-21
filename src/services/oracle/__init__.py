"""Oracle service package for contextual feedback personalities.

Per plan.md for 007-contextual-oracle-feedback.
"""

from src.services.oracle.loader import OracleLoader
from src.services.oracle.manager import OracleManager

__all__ = ["OracleLoader", "OracleManager"]
