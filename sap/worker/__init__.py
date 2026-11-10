"""
Worker.

This package regroups all common helpers for background workers.

The modules of this package define what lambdas and crons process, whatever runs them.
Pick the runner with its extra:
- `sap.worker.taskiq` runs them with Taskiq: `pip install sapx[taskiq]`;
- `sap.worker.celery` runs them with Celery: `pip install sapx[celery]`.
"""
