"""
Run an event dispatcher until the process is stopped.

Usage: `python -m sap.worker.taskiq AppMain.taskiq.lambdas:dispatcher`.
"""

import asyncio
import logging
import sys

from .dispatcher import load_dispatcher

if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(load_dispatcher(sys.argv[1]).run())
