"""Out-of-band work: SMS send, image processing, expiry sweeps, stats.

The Arq worker shares the repository with the API — same models, same
services — but a different entrypoint (``arq_worker.WorkerSettings``).
"""
