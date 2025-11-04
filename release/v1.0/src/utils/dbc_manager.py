# -*- coding: utf-8 -*-
"""
DBC Manager - Manages multiple DBC files for the application
"""
import os
from pathlib import Path
from typing import Dict, Optional
import logging

from src.core.dbc_parser import DBCParser

logger = logging.getLogger(__name__)


class DBCManager:
    """
    Manages multiple DBC files and provides parsers for them
    """

    def __init__(self, dbc_directory: str = "."):
        """
        Initialize DBC Manager

        Args:
            dbc_directory: Directory containing DBC files
        """
        self.dbc_directory = dbc_directory
        self.parsers: Dict[str, DBCParser] = {}
        self.default_dbc = 'vw_mqb.dbc'

    def load_dbc(self, dbc_file: str) -> DBCParser:
        """
        Load a DBC file and create parser

        Args:
            dbc_file: DBC file name or path

        Returns:
            DBCParser instance
        """
        # Check if already loaded
        if dbc_file in self.parsers:
            logger.debug(f"DBC file already loaded: {dbc_file}")
            return self.parsers[dbc_file]

        # Find full path
        if os.path.isabs(dbc_file):
            dbc_path = dbc_file
        else:
            dbc_path = os.path.join(self.dbc_directory, dbc_file)

        if not os.path.exists(dbc_path):
            raise FileNotFoundError(f"DBC file not found: {dbc_path}")

        # Load and cache
        parser = DBCParser(dbc_path)
        self.parsers[dbc_file] = parser
        logger.info(f"Loaded DBC file: {dbc_file}")

        return parser

    def get_parser(self, dbc_file: Optional[str] = None) -> DBCParser:
        """
        Get parser for specified DBC file, or default if not specified

        Args:
            dbc_file: DBC file name, or None for default

        Returns:
            DBCParser instance
        """
        if dbc_file is None:
            dbc_file = self.default_dbc

        return self.load_dbc(dbc_file)

    def set_default_dbc(self, dbc_file: str):
        """Set default DBC file"""
        self.default_dbc = dbc_file
        logger.info(f"Set default DBC: {dbc_file}")

    def scan_dbc_directory(self) -> list:
        """
        Scan directory for DBC files

        Returns:
            List of DBC file names found
        """
        dbc_files = []
        try:
            for file in os.listdir(self.dbc_directory):
                if file.endswith('.dbc'):
                    dbc_files.append(file)
            logger.info(f"Found {len(dbc_files)} DBC files in {self.dbc_directory}")
        except Exception as e:
            logger.error(f"Failed to scan DBC directory: {e}")

        return dbc_files

    def get_loaded_dbc_files(self) -> list:
        """Get list of currently loaded DBC files"""
        return list(self.parsers.keys())

    def unload_dbc(self, dbc_file: str):
        """Unload a DBC file from memory"""
        if dbc_file in self.parsers:
            del self.parsers[dbc_file]
            logger.info(f"Unloaded DBC file: {dbc_file}")

    def clear_all(self):
        """Clear all loaded DBC files"""
        self.parsers.clear()
        logger.info("Cleared all DBC parsers")
