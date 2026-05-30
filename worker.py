"""Background export worker.

Polls the `export_jobs` queue and generates export files on disk, decoupled
from the gunicorn web workers so that very large exports cannot hit a request
timeout. Run as its own process / container:

    python worker.py

Importing `app` runs initialize_app(), which self-migrates the database
(creating the export_jobs table if missing), exactly like the web service.
The RAMAN_ROLE=worker env var tells initialize_app() to skip the backup
scheduler so backups are not run twice.
"""
import os
import time
import traceback

# Must be set before importing app so initialize_app() skips the scheduler.
os.environ.setdefault('RAMAN_ROLE', 'worker')

import app  # noqa: E402  (import after setting env var on purpose)

POLL_SECONDS = int(os.getenv('EXPORT_POLL_SECONDS', '5'))
SWEEP_SECONDS = int(os.getenv('EXPORT_SWEEP_SECONDS', '600'))


def main():
    print("[export-worker] started; polling every "
          f"{POLL_SECONDS}s, sweeping every {SWEEP_SECONDS}s")

    # On startup, requeue anything left 'running' by a previous crashed worker.
    try:
        app.reclaim_stale_export_jobs()
    except Exception:
        traceback.print_exc()

    last_sweep = 0.0
    while True:
        try:
            job_id = app.claim_next_export_job()
            if job_id:
                print(f"[export-worker] processing job {job_id}")
                app.process_export_job(job_id)
            else:
                time.sleep(POLL_SECONDS)

            now = time.time()
            if now - last_sweep > SWEEP_SECONDS:
                last_sweep = now
                app.reclaim_stale_export_jobs()
                app.sweep_expired_exports()
        except KeyboardInterrupt:
            print("[export-worker] shutting down")
            break
        except Exception:
            traceback.print_exc()
            time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
