# -*- coding: utf-8 -*-
"""
Signal Calculator
Engine for calculating custom computed signals
"""
import re
import math
import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)


class SignalCalculator:
    """Signal calculation engine"""

    def __init__(self, db_manager):
        """
        Initialize calculation engine

        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
        self.custom_signals = {}  # {signal_name: formula}
        self.load_custom_signals()

    def load_custom_signals(self):
        """Load custom calculated signals from database"""
        try:
            cursor = self.db_manager.cursor
            cursor.execute("""
                SELECT signal_name, formula
                FROM custom_signals
            """)

            self.custom_signals = {}
            for signal_name, formula in cursor.fetchall():
                self.custom_signals[signal_name] = formula

            logger.info(f"Loaded {len(self.custom_signals)} custom signal formulas")

        except Exception as e:
            logger.error(f"Failed to load custom signals: {e}")
            self.custom_signals = {}

    def is_custom_signal(self, signal_name: str) -> bool:
        """
        Check if signal is a custom calculated signal

        Args:
            signal_name: Signal name

        Returns:
            True if it's a custom calculated signal
        """
        return signal_name in self.custom_signals

    def get_formula(self, signal_name: str) -> str:
        """
        Get calculation formula for signal

        Args:
            signal_name: Signal name

        Returns:
            Calculation formula, or None if not a custom signal
        """
        return self.custom_signals.get(signal_name)

    def extract_dependencies(self, formula: str) -> List[str]:
        """
        Extract dependent signal names from formula

        Args:
            formula: Calculation formula

        Returns:
            List of dependent signal names
        """
        # Signal name formats: messageType.fieldName or CAN_0xXXX_SignalName
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*|CAN_0x[0-9A-Fa-f]+_[a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = re.findall(pattern, formula)
        return list(set(matches))  # Remove duplicates

    def calculate_signal(self, signal_name: str, segment_id: int,
                        start_time_ns: int, end_time_ns: int) -> List[Tuple[int, float]]:
        """
        Calculate time series data for custom signal

        Args:
            signal_name: Custom signal name
            segment_id: Segment ID
            start_time_ns: Start time (nanoseconds)
            end_time_ns: End time (nanoseconds)

        Returns:
            Time series data list [(log_time_ns, value), ...]
        """
        formula = self.custom_signals.get(signal_name)
        if not formula:
            logger.error(f"Signal {signal_name} is not a custom signal")
            return []

        try:
            # Extract dependent signals
            dependencies = self.extract_dependencies(formula)

            if not dependencies:
                logger.warning(f"No dependencies found in formula: {formula}")
                return []

            # Query data for all dependent signals
            signal_data = {}
            for dep_signal in dependencies:
                data = self.db_manager.get_timeseries_data(
                    segment_id, dep_signal, start_time_ns, end_time_ns
                )
                if data:
                    signal_data[dep_signal] = {row[0]: row[1] for row in data}  # {time_ns: value}
                else:
                    logger.warning(f"No data for dependency signal: {dep_signal}")
                    return []

            # Find union of all timestamps
            all_timestamps = set()
            for timestamps in signal_data.values():
                all_timestamps.update(timestamps.keys())

            all_timestamps = sorted(all_timestamps)

            # Calculate formula for each timestamp
            results = []
            for timestamp in all_timestamps:
                # Prepare signal values for this timestamp
                values = {}
                skip = False

                for dep_signal in dependencies:
                    if timestamp in signal_data[dep_signal]:
                        values[dep_signal] = signal_data[dep_signal][timestamp]
                    else:
                        # Skip if missing any dependent signal value at this timestamp
                        skip = True
                        break

                if skip:
                    continue

                # Calculate formula
                try:
                    result = self._evaluate_formula(formula, values)
                    results.append((timestamp, result))
                except Exception as e:
                    logger.debug(f"Failed to calculate at time {timestamp}: {e}")
                    continue

            logger.info(f"Calculated {len(results)} data points for {signal_name}")
            return results

        except Exception as e:
            logger.error(f"Failed to calculate signal {signal_name}: {e}")
            return []

    def _evaluate_formula(self, formula: str, signal_values: Dict[str, float]) -> float:
        """
        Evaluate formula

        Args:
            formula: Calculation formula
            signal_values: Signal value dictionary {signal_name: value}

        Returns:
            Calculation result
        """
        # Replace signal names with actual values
        eval_formula = formula
        for sig_name, value in signal_values.items():
            # Use regex to ensure complete signal name matching
            pattern = r'\b' + re.escape(sig_name) + r'\b'
            eval_formula = re.sub(pattern, str(value), eval_formula)

        # Safe math function environment
        safe_dict = {
            'sqrt': math.sqrt,
            'abs': abs,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'atan2': math.atan2,
            'exp': math.exp,
            'log': math.log,
            'log10': math.log10,
            'pow': pow,
            'pi': math.pi,
            'e': math.e,
            '__builtins__': {}
        }

        # Evaluate formula
        try:
            result = eval(eval_formula, safe_dict)
            return float(result)
        except Exception as e:
            raise ValueError(f"Formula calculation error: {str(e)}")
