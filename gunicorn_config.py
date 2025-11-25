# gunicorn_config.py
# Production configuration for Raman Medical Research System

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
# Formula: (2 × CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"  # Options: sync, gevent, eventlet
worker_connections = 1000

# Worker lifecycle
max_requests = 1000  # Restart worker after this many requests (prevents memory leaks)
max_requests_jitter = 50  # Add randomness to prevent simultaneous restarts
timeout = 15  # Request timeout in seconds (increase for long-running operations)
graceful_timeout = 30  # Time to wait for workers to finish before force kill
keepalive = 2  # Keep-alive connections

# Preload the application
preload_app = True

# Logging
accesslog = "-"  # Log to stdout (Docker will capture)
errorlog = "-"   # Log errors to stderr
loglevel = "info"  # Options: debug, info, warning, error, critical
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Make sure Python prints are visible
capture_output = True
enable_stdio_inheritance = True

# Process naming
proc_name = "raman_medical_research"

# Server mechanics
daemon = False  # Don't daemonize (Docker/systemd handles this)
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Environment
raw_env = [
    f"FLASK_ENV={os.getenv('FLASK_ENV', 'production')}",
]

# SSL Configuration (if not using Nginx for SSL termination)
# Uncomment if you want Gunicorn to handle SSL directly
# keyfile = "/path/to/ssl/key.pem"
# certfile = "/path/to/ssl/cert.pem"
# ssl_version = ssl.PROTOCOL_TLS
# cert_reqs = ssl.CERT_NONE
# ca_certs = "/path/to/ca_certs.pem"
# ciphers = "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256"

# Development vs Production Settings
if os.getenv('FLASK_ENV') == 'development':
    # Development settings
    workers = 2
    reload = True  # Auto-reload on code changes
    loglevel = "debug"
    accesslog = None  # Don't log every request in development
else:
    # Production settings
    reload = False
    loglevel = "info"

# Security headers (if not handled by Nginx)
# secure_scheme_headers = {
#     'X-FORWARDED-PROTOCOL': 'ssl',
#     'X-FORWARDED-PROTO': 'https',
#     'X-FORWARDED-SSL': 'on'
# }

# Forwarded allow IPs (when behind proxy)
forwarded_allow_ips = '*'  # Trust all proxies (Nginx)

# Pre-fork callbacks
def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"Starting Raman Medical Research System with {workers} workers")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    print("Reloading workers...")

def when_ready(server):
    """Called just after the server is started."""
    print(f"Server is ready. Listening on {bind}")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    print("Shutting down Raman Medical Research System")

# Worker callbacks
def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker {worker.pid} spawned")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    pass

def worker_int(worker):
    """Called when a worker received the SIGINT or SIGQUIT signal."""
    print(f"Worker {worker.pid} received termination signal")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    print(f"Worker {worker.pid} aborted")

def pre_exec(server):
    """Called just before a new master process is forked."""
    print("Forking new master process")

def pre_request(worker, req):
    """Called just before a worker processes the request."""
    worker.log.debug(f"{req.method} {req.path}")

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request."""
    pass

# Paste Deployment configuration (if using)
# [server:main]
# use = egg:gunicorn#main
# host = 0.0.0.0
# port = 5000

# Notes:
# - Increase 'workers' if you have more CPU cores
# - Increase 'timeout' if you have long-running requests (e.g., exports)
# - Use 'gevent' worker_class for async I/O operations (install gevent first)
# - Monitor memory usage and adjust max_requests if you see memory leaks
# - Use 'debug' log level only for troubleshooting, not in production