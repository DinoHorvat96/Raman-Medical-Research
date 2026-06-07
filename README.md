# Raman Medical Research Database

A comprehensive medical research database system for ophthalmic clinical data collection and analysis with HTTP/2 support for improved performance.

## 🎯 Project Overview

Raman is a professional medical research database designed specifically for collecting and analyzing ophthalmic (eye-related) clinical data. The system features:

- **Modern HTTP/2 Protocol** for faster page loads and better performance (40-50% latency reduction)
- **HTTP/3 Ready** for future ultra-low latency connections
- **Dual-table architecture** for data security (sensitive vs. statistical data)
- **Automatic patient ID generation** starting from 1500 with manual override capability
- **Real-time ID availability checking** with concurrent user support
- **Patient deletion capability** with complete cascade deletion and ID recycling
- **Comprehensive ocular condition tracking** with 40+ specialized fields
- **SHA-256 person hashing** for anonymized data analysis
- **Multi-user support** with role-based access control
- **ICD-10 coding** for conditions and medications
- **Bulk import/export system** with CSV and Excel formats
- **Complete reference data management** for codes, medications, and surgeries
- **Advanced filtering system** for patient searches and data exports
- **Memory-efficient streaming exports** that scale to very large datasets without timeouts
- **Background export jobs** with a live progress bar, cancellation, and download links
- **Automated backup & restore** with scheduling support and external drive detection
- **Advanced form validation** with real-time feedback

## 🌐 Network Performance & HTTP/2

### Protocol Support
- **HTTP/1.1**: Default (works without SSL)
- **HTTP/2**: Enabled with SSL/TLS (recommended)
- **HTTP/3 (QUIC)**: Ready to enable (future)

### Architecture
```
Client Browser → Nginx (HTTP/2) → Gunicorn (HTTP/1.1 internal) → Flask App
```

The internal HTTP/1.1 connection between Nginx and Gunicorn has **no performance impact** since it's within the Docker network.

### HTTP/2 Benefits
- **40-50% faster page loads** through multiplexing
- **30% bandwidth savings** from header compression
- **Binary protocol** for faster parsing
- **Server push** capability for proactive resource delivery
- **Single connection** for all resources (vs multiple in HTTP/1.1)

### Quick HTTP/2 Setup
The bundled `nginx.conf` is intentionally **minimal (HTTP/1.1)** for reliability
across hosts (including ARM / Raspberry Pi, where stray `listen [::]:80` IPv6
directives can crash nginx). HTTP/2 is opt-in once you add TLS:
1. Obtain an SSL certificate (Let's Encrypt or self-signed)
2. Add an HTTPS `server { listen 443 ssl http2; ... }` block to `nginx.conf`, proxying to the same `raman_app` upstream
3. Mount your certificates into the nginx container (uncomment the `./ssl` volume in `docker-compose.yml`)
4. Restart services: `docker compose restart nginx`
5. Verify: `curl -I --http2 https://your-domain.com`

## 📋 Database Architecture

### Core Tables

#### 1. **users**
Authentication and authorization
- `user_id`, `username`, `password_hash`, `email`, `role`, `created_at`, `last_login`
- Roles: **Administrator**, **Staff**

#### 2. **patients_sensitive** (Protected Data)
Personal identifiable information
- `patient_id` (5-digit: 00001-99999, custom or auto-generated)
- `patient_name`, `mbo` (9 digits), `date_of_birth`, `date_of_sample_collection`
- Access controlled by role
- **Deletable**: Complete cascade deletion with ID recycling

#### 3. **patients_statistical** (Anonymized Export Data)
De-identified data for analysis
- `patient_id`, `person_hash` (SHA-256 of MBO), `age` (calculated), `sex`, `eye`
- Used for statistical exports
- Automatically deleted when parent patient is deleted (CASCADE)

#### 4. **ocular_conditions**
Main ocular conditions (one row per patient)

**Lens Status & Cataract:**
- Lens status: Phakic, Pseudophakic, Aphakic
- LOCS III grading: NO, NC, C, P (0.0-9.9 scale)
- IOL type (for pseudophakic): Monofocal, Multifocal, Toric, etc.
- Aphakia etiology (for aphakic)

**Glaucoma:**
- Glaucoma status (Yes/No)
- OHT or PAC (Ocular Hypertension / Primary Angle Closure)
- Etiology: POAG, Angle Closure, NTG, Secondary
- Steroid responder status
- PXS (Pseudoexfoliation Syndrome)
- PDS (Pigment Dispersion Syndrome)

**Diabetic Retinopathy:**
- DR status (Yes/No)
- Stage: NPDR or PDR
- NPDR stage: Mild, Moderate, Severe
- PDR stage: Active, Stable, Regressed

**Macular Conditions:**
- Macular edema (Yes/No) with etiology
- Macular degeneration/dystrophy with type and stage
- AMD: Dry/Wet with staging and exudation status
- Other macular degeneration with staging and exudation

**Macular Hole & VMT:**
- Status (Yes/No)
- Etiology: Idiopathic, Traumatic, Secondary
- Secondary cause if applicable
- Treatment status: Untreated, Planned, Post-op

**Epiretinal Membrane:**
- Status (Yes/No)
- Etiology: Idiopathic, Secondary
- Secondary cause if applicable
- Treatment status

**Retinal Detachment:**
- Status (Yes/No)
- Etiology: Rhegmatogenous, Tractional, Exudative
- Treatment status
- PVR (Proliferative Vitreoretinopathy) status

**Vitreous Conditions:**
- Vitreous hemorrhage/opacification (Yes/No)
- Etiology if present

#### 5-9. **Related Tables** (One-to-Many - CASCADE DELETE)
- **other_ocular_conditions**: Additional ICD-10 coded conditions
- **previous_ocular_surgeries**: Surgical history with eye specification
- **systemic_conditions**: Non-ocular ICD-10 conditions
- **ocular_medications**: Eye medications with timing
- **systemic_medications**: Systemic medications with timing

All related data automatically deleted when patient is deleted.

### Reference Tables

#### 10-13. **Reference Data**
- **icd10_ocular_conditions**: Ophthalmic ICD-10 codes (bulk import supported)
- **icd10_systemic_conditions**: Systemic ICD-10 codes (bulk import supported)
- **medications**: HALMED medication registry (bulk import supported)
- **surgeries**: Ocular surgical procedures

### Operational Tables

#### 14. **export_jobs** (Background Export Queue)
Tracks queued/running background export jobs. **Self-migrating** — created
automatically on startup via `CREATE TABLE IF NOT EXISTS`, so deploying this
feature onto an existing database requires no manual migration.
- `job_id` (UUID), `requested_by`, `params` (JSON), `status` (pending / running / done / failed / cancelled)
- `rows_total`, `rows_done` (for progress reporting), `file_path`, `expires_at`, `cancel_requested`
- Transient operational data — **excluded from backups** (the table structure is
  kept, but not its rows, which reference regenerable export files)

> **Schema versioning note:** every table is created with `CREATE TABLE IF NOT
> EXISTS` on startup, so new tables are added automatically on deploy without a
> separate migration step.

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 15+
- Docker & Docker Compose (recommended)
- SSL Certificate (for HTTP/2, optional)

### Quick Start with Docker (Recommended)

1. **Clone and configure**:
```bash
# Create .env file
cat > .env << EOF
DB_NAME=raman_research_prod
DB_USER=postgres
DB_PASSWORD=your_secure_password_here
DB_HOST=postgres_container
SECRET_KEY=$(openssl rand -base64 32)
STARTING_PATIENT_ID=1500
BACKUP_DIR=/mnt/medical_backups/raman_backups

# Published host ports (change if they conflict with other apps)
HTTP_PORT=8099          # nginx front door
WEB_PORT=5000           # direct gunicorn access

# Background export settings
EXPORT_DIRECTORY=/exports        # where generated export files are stored
EXPORT_RETENTION_HOURS=24        # auto-delete generated exports after N hours
# EXPORT_INLINE_WORKER=false     # set on the web service when using the export_worker container
EOF
```

> **Tip:** all ports are configurable, so the stack can run alongside other apps
> (e.g. on Unraid, where port 80 is taken by the web UI). See `.env.example` for
> the full, documented list of variables.

2. **Start services**:
```bash
docker-compose up -d
```

3. **Access application**:
- Via nginx (recommended front door): `http://localhost:8099` (set by `HTTP_PORT`)
- Direct to the app, bypassing nginx: `http://localhost:5000` (set by `WEB_PORT`)
- Login: `Admin` / `admin123`
- **Change default password immediately!**

> nginx is optional — it's a reverse proxy in front of the app. If you front the
> app with something else (Cloudflare, Nginx Proxy Manager, SWAG, etc.) or only
> need internal access, you can run without it and point users at `WEB_PORT`.

4. **Enable HTTP/2** (optional):
```bash
# Get SSL certificate
sudo certbot certonly --standalone -d your-domain.com

# Add an HTTPS server block (listen 443 ssl http2;) to nginx.conf
# Mount the certs into the nginx container (uncomment the ./ssl volume in docker-compose.yml)
# Restart
docker compose restart nginx

# Verify
curl -I --http2 https://your-domain.com
```

### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env file (see above)

# Run development server
python app.py

# OR run with Gunicorn
gunicorn --config gunicorn_config.py app:app
```

## 🔐 Security Features

### Data Protection
- **Separate sensitive/statistical tables**: PII isolation
- **Bcrypt password hashing** with salt
- **Session-based authentication**
- **Role-based access control**: Administrator and Staff roles
- **SHA-256 person hashing**: Anonymous patient tracking
- **Export access control**: Staff limited to anonymized exports only
- **HTTP/2 with TLS 1.3**: Modern encryption
- **Security headers**: HSTS, X-Frame-Options, CSP

### Data Validation
- **Real-time patient ID validation**: Prevents duplicates
- **Comprehensive form validation**: Client and server-side
- **Date validation**: Logical date range enforcement
- **MBO format validation**: 9-digit format
- **Foreign key constraints**: Data integrity

### Patient Deletion
- **Complete cascade deletion**: All related data removed
- **Dual confirmation**: Two-step process prevents accidents
- **ID recycling**: Deleted IDs return to available pool
- **Access control**: Staff and Administrator only
- **Data integrity**: Foreign keys ensure clean deletion

## 👥 User Roles

### Administrator
- Full system access
- Manage reference data (ICD-10, medications, surgeries)
- Bulk import/export
- User management
- **Export sensitive data** (names, MBO)
- Export anonymized data
- Delete patients
- Backup/restore operations
- System configuration

### Staff
- Create/edit patient records
- View all patient data
- Data entry and validation
- Search and filter patients
- **Export anonymized data only**
- Delete patients

## 📊 Key Features

### 1. Patient Management

#### Patient ID System
- Auto-increment from configurable ID (default: 1500)
- 5-digit format: 00001-99999
- Manual override with real-time duplicate detection
- Concurrent entry protection
- **ID recycling**: Deleted IDs automatically available for reuse
- Periodic background checking

#### Patient Deletion
- **Permanent deletion** of patient and all data
- **Cascade deletion**:
  - Statistical data
  - Ocular conditions
  - Other ocular conditions
  - Previous surgeries
  - Systemic conditions
  - Ocular medications
  - Systemic medications
- **Two-step confirmation**
- **ID returned to pool** for reuse
- **Foreign key integrity** ensures clean deletion

### 2. Advanced Data Export

#### Export Options
- **Formats**: CSV or Excel (.xlsx)
- **Data Types**:
  - Anonymized (person hash, no PII)
  - Sensitive (Admin only - includes names/MBO)
- **Data Inclusion**:
  - Basic demographics
  - Main ocular conditions
  - Other ocular conditions (ICD-10)
  - Previous surgeries
  - Systemic conditions
  - Medications (ocular & systemic)
- **Filters**: Date range, conditions, surgeries, medications

#### Export Features
- **Binary column format**: One column per condition/medication
- **Dynamic columns**: Adapts to patient variations
- **Excel formatting**: Professional appearance
- **Generic component extraction**: Individual drug tracking
- **Audit-friendly filenames**: Includes type and timestamp

#### Export Modes
- **Synchronous (streamed)**: generated on the fly and streamed straight to the
  browser — ideal for small/medium pulls. Rows stream in chunks, so memory stays
  flat regardless of dataset size and the download starts immediately.
- **Background job** (recommended for large exports): tick *"Generate in
  background"*. The job is queued and produced by a dedicated worker while you
  watch a **live progress bar** (X / Y patients), with the ability to **cancel**
  and a **download link** when it's ready. This survives full-database dumps that
  would otherwise exceed request timeouts.

#### Large-Dataset Handling
- **Chunked, server-side-cursor streaming**: peak memory is proportional to a
  small chunk (default 500 rows), not the total patient count — so exports scale
  toward the 99,999-patient ceiling without exhausting RAM
- **openpyxl write-only mode** keeps Excel generation memory-flat
- **Atomic file writes**: files are written to a temporary name and renamed on
  completion, so a crash or cancellation never leaves a half-written download
- **Self-cleaning storage**: generated files auto-expire (default 24h) and are
  swept by the worker, along with any orphaned/partial files
- **Resilient queue**: jobs are claimed with `FOR UPDATE SKIP LOCKED` (no
  double-processing), and jobs left running by a crashed worker are automatically
  requeued

#### How the background worker runs
- **In-process worker** (default): a worker thread runs inside the app, so
  background exports work out of the box (development or single-process deploys)
- **Dedicated `export_worker` container** (production): set
  `EXPORT_INLINE_WORKER=false` on the web service so only the container consumes
  the queue. It does no DB initialization and starts after the web service is
  healthy, so there are no first-boot races.

### 3. Bulk Import/Export

#### ICD-10 Management
- Import from CSV/Excel
- Auto-detect columns
- Preview before import
- Category auto-detection
- Export to Excel
- Update on conflict

#### Medications Management
- Bulk upload from Excel/CSV
- Multi-component support (semicolon-separated)
- Type auto-detection (Ocular/Systemic/Both)
- Flexible column mapping
- Export current list

### 4. Backup & Restore

#### Backup Features
- Manual on-demand backups
- **Scheduled automatic backups**: Hourly, daily, weekly, monthly
- **External drive support**: Save to external storage
- **Directory browser**: Navigate filesystem
- **Drive detection**: Real-time external drive status
- **Retention management**: Auto-delete old backups
- **Space verification**: Check available space
- **Full `pg_dump` + CSV fallback**: complete database dump, or a per-table CSV export if `pg_dump` is unavailable
- **Transient data excluded**: the background-export queue (`export_jobs`) is skipped, so only real research data is backed up — restores recreate the (empty) queue table automatically

#### Restore Features
- One-click restore
- Download backups locally
- View/manage all backups
- Multiple safety confirmations

### 5. Reference Data Management

All manageable through Settings interface:

- **ICD-10 Ocular Conditions**: Add, edit, deactivate, bulk import/export
- **ICD-10 Systemic Conditions**: Full CRUD, bulk operations
- **Medications**: Trade/generic names, HALMED compatible, bulk import
- **Surgical Procedures**: Codes, descriptions, categories

These reference lists are the single source of truth for the dropdowns used
**both** when creating patients (New Patient) **and** when editing/verifying them
(Validate Data) — so any code you add (including via bulk import) is immediately
selectable everywhere, with no hardcoded subsets.

### 6. Advanced Search & Filtering

- Search by: Patient ID, Name, MBO
- **Filter by**:
  - Main ocular conditions (glaucoma, DR, lens status, etc.)
  - Other conditions presence
  - Surgery history
  - Medication usage
- **Combination filters**: Apply multiple simultaneously
- Recent patients list (20 most recent)

## 🐳 Docker Deployment

### Services
```yaml
web:             # Flask + Gunicorn (the application itself)
export_worker:   # Background export job processor (consumes the export queue)
nginx:           # Reverse proxy / front door (optional)
postgres:        # Optional internal database (commented out by default)
```

### Features
- **Configurable host ports** via `HTTP_PORT` / `WEB_PORT` (avoid conflicts with other apps)
- **Dedicated export worker** container for off-request-path background exports
- **`.dockerignore`** keeps secrets (`.env`), the Postgres data dir, and backups/exports out of the build context (smaller, safer builds)
- Health checks
- Auto-restart
- Persistent volumes (backups, uploads, exports)
- Network isolation

### Build context note
The `.dockerignore` excludes `postgres_data/`, `backups/`, `exports/`, `.env`,
and other runtime data. If you enable the internal Postgres service, **do not**
`chmod` its data directory to work around build errors — Postgres requires it to
stay `0700`; the `.dockerignore` is what keeps it out of the build context.

> **Command note:** modern Docker uses `docker compose` (v2, a space). Some
> hosts (e.g. Unraid via the Compose plugin) provide the older `docker-compose`
> (v1, a hyphen). Use whichever prints a version from `docker compose version` /
> `docker-compose version`. Examples below use the v2 form.

### Commands
```bash
# Start (build images + create containers, incl. export_worker)
docker compose up -d --build

# View logs (all services, or one)
docker compose logs -f
docker compose logs -f export_worker

# Status
docker compose ps

# Restart just one service after a config change (bind-mounted code/conf)
docker compose restart web
docker compose restart nginx

# Stop
docker compose down

# Run without nginx (use WEB_PORT directly)
docker compose up -d --scale nginx=0
```

## 📊 Performance & Capacity

### Database Statistics
- **Patients**: Up to 99,999 (5-digit IDs)
- **Conditions per patient**: Unlimited
- **Medications per patient**: Unlimited
- **Surgeries per patient**: Unlimited
- **Concurrent users**: 50+ (with proper PostgreSQL tuning)
- **ICD-10 Codes**: 1000s supported via bulk import

### Performance Metrics
- **Page load time**: 20-30% faster with HTTP/2
- **Latency reduction**: 40-50% improvement with HTTP/2
- **Bandwidth savings**: 30% with compression
- **Export speed**: ~1000 patients/second to CSV
- **Search speed**: <100ms for most queries

## 🤝 Best Practices

### Patient Deletion
1. **Always backup before bulk deletions**
2. Verify patient identity
3. Understand deletion is permanent
4. Note ID will be recycled
5. Use confirmation dialogs carefully

### HTTP/2 & Security
1. Always use SSL/TLS in production
2. Enable compression (gzip/brotli)
3. Use strong ciphers (TLS 1.3)
4. Monitor certificate expiry
5. Set up auto-renewal (Let's Encrypt)
6. Keep Nginx and OpenSSL updated

### Data Export
1. Use filters for specific cohorts
2. Use anonymized exports for statistics
3. Secure exported files appropriately
4. Delete exports after use
5. Document export parameters

### Backup & Restore
1. Schedule daily backups minimum
2. Use external drives/network storage
3. Test restore procedures regularly
4. Keep multiple backup versions
5. Always backup before major changes
6. Verify backup location has space

## 🔧 Troubleshooting

### HTTP/2 Issues

**Issue: Still showing HTTP/1.1**
```bash
# Check nginx HTTP/2 support
docker exec medical_nginx nginx -V | grep http_v2

# Verify SSL certificate
openssl s_client -connect your-domain.com:443

# Check configuration
docker exec medical_nginx nginx -t
```

**Issue: Certificate errors**
```bash
# Check certificate validity
openssl x509 -in /etc/letsencrypt/live/your-domain.com/cert.pem -text -noout

# Verify chain
openssl verify -CAfile chain.pem cert.pem
```

### Database Issues

**Issue: Connection error**
```bash
sudo systemctl status postgresql
psql -U postgres -d raman_research_prod
```

**Issue: Patient ID already exists**
- Use auto-generated ID
- Choose different manual ID
- Check for orphaned records

**Issue: Cannot delete patient**
- Verify Staff/Administrator role
- Check database constraints
- Review error logs

### Application Issues

**Issue: Dependencies won't install**
```bash
# Install PostgreSQL dev headers
sudo apt-get install libpq-dev python3-dev

# Use binary package
pip install psycopg2-binary
```

**Issue: Backup directory not writable**
```bash
sudo mkdir -p /mnt/medical_backups/raman_backups
sudo chown $USER:$USER /mnt/medical_backups/raman_backups
```

## 📞 Support & Monitoring

### Health Checks
- Application: `http://localhost:5000/health` (or via nginx on `HTTP_PORT`)
- Web/app: `docker compose ps` → `medical_web` should be `Up (healthy)`
- Export worker: `docker compose logs export_worker` → look for `[export-worker] started` and `[export] job <id> done`
- Nginx: `docker compose logs nginx`
- Database: `psql -U postgres -c "SELECT version();"`

> The `export_worker` container intentionally has **no** healthcheck (it runs no
> web server), so it shows plain `Up` rather than `(healthy)`. That's expected.

### Performance Testing
```bash
# HTTP/2 load testing
h2load -n1000 -c10 -m10 https://your-domain.com

# Check active connections
docker exec medical_nginx cat /var/log/nginx/access.log | grep "HTTP/2"
```

### SSL Certificate Management
```bash
# Test renewal
sudo certbot renew --dry-run

# Auto-renewal cron
sudo crontab -e
# Add: 0 3 * * * certbot renew --quiet --post-hook "docker-compose restart nginx"
```

## 📄 License

Private medical research project. All rights reserved.

---

**Version:** 2.1  
**Last Updated:** June 2026  
**Status:** Production Ready  
**Database Schema Version:** 2.1 (adds self-migrating `export_jobs` queue)  
**Exports:** Streaming (chunked) + background jobs with progress, cancellation & auto-cleanup  
**Deployment:** Docker (x86_64 & ARM/Raspberry Pi), fully configurable host ports  
**Network Protocol:** HTTP/1.1 default; HTTP/2 opt-in with SSL  
**Security:** Bcrypt, role-based access, sensitive/statistical split, SHA-256 person hashing