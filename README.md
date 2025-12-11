# Raman Medical Research Database

A comprehensive medical research database system for ophthalmic clinical data collection and analysis.

## 🎯 Project Overview

Raman is a professional medical research database designed specifically for collecting and analyzing ophthalmic (eye-related) clinical data. The system features:

- **Dual-table architecture** for data security (sensitive vs. statistical data)
- **Automatic patient ID generation** starting from 1500 with manual override capability
- **Real-time ID availability checking** with concurrent user support
- **Comprehensive ocular condition tracking** with 40+ specialized fields
- **SHA-256 person hashing** for anonymized data analysis
- **Multi-user support** with role-based access control
- **ICD-10 coding** for conditions and medications
- **Bulk import/export system** with CSV and Excel formats
- **Complete reference data management** for codes, medications, and surgeries
- **Advanced filtering system** for patient searches and data exports
- **Automated backup & restore** with scheduling support
- **Advanced form validation** with real-time feedback

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

#### 3. **patients_statistical** (Anonymized Export Data)
De-identified data for analysis
- `patient_id`, `person_hash` (SHA-256 of MBO), `age` (calculated), `sex`, `eye`
- Used for statistical exports

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

#### 5. **other_ocular_conditions** (One-to-Many)
Additional ICD-10 coded ocular conditions
- `patient_id`, `icd10_code`, `eye`
- Unlimited entries per patient

#### 6. **previous_ocular_surgeries** (One-to-Many)
Surgical history
- `patient_id`, `surgery_code`, `eye`
- Includes all ocular surgeries and laser treatments

#### 7. **systemic_conditions** (One-to-Many)
Non-ocular ICD-10 conditions
- `patient_id`, `icd10_code`
- Diabetes, hypertension, etc.

#### 8. **ocular_medications** (One-to-Many)
Eye medications with timing
- `patient_id`, `trade_name`, `generic_name`, `eye`, `last_application_days`

#### 9. **systemic_medications** (One-to-Many)
Systemic medications
- `patient_id`, `trade_name`, `generic_name`, `last_application_days`

### Reference Tables

#### 10. **icd10_ocular_conditions**
Ophthalmic ICD-10 codes
- `id`, `code`, `description`, `category`, `active`
- Supports bulk import from Excel/CSV

#### 11. **icd10_systemic_conditions**
Systemic ICD-10 codes
- `id`, `code`, `description`, `category`, `active`
- Supports bulk import from Excel/CSV

#### 12. **medications**
HALMED medication registry
- `id`, `trade_name`, `generic_name`, `medication_type` (Ocular/Systemic/Both), `active`
- Supports multi-component medications (separated by semicolon)
- Supports bulk import from Excel/CSV

#### 13. **surgeries**
Ocular surgical procedures
- `id`, `code`, `description`, `category`, `active`

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 15+
- pip

### Installation

1. **Clone/create the project structure**:
```
raman/
├── app.py
├── requirements.txt
├── .env
├── gunicorn_config.py
├── docker-compose.yml
├── nginx.conf
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── new_patient.html
│   ├── edit_patient.html
│   ├── validate_data.html
│   ├── export_data.html
│   ├── settings.html
│   ├── settings_backup.html
│   ├── settings_icd10_ocular.html
│   ├── settings_icd10_systemic.html
│   ├── settings_medications.html
│   ├── settings_surgeries.html
│   ├── icd10_bulk_upload.html
│   ├── medications_bulk_upload.html
│   └── user_management.html
└── README.md
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

Required packages:
```
Flask==3.0.3
Flask-Bcrypt==1.0.1
psycopg2-binary==2.9.9
python-dotenv==1.0.1
pandas==2.3.3
openpyxl==3.1.5
gunicorn==23.0.0
schedule==1.2.2
```

3. **Configure database** (create `.env` file):
```env
# Database Configuration
DB_NAME=raman_research_prod
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432

# Flask Secret Key (change this to a random string in production)
SECRET_KEY=change-this-to-a-random-secret-key # openssl rand -base64 32

# Patient ID Configuration
# Starting patient ID for auto-assignment
STARTING_PATIENT_ID=1500

# Backup Configuration
BACKUP_DIR=/mnt/medical_backups/raman_backups
BACKUP_RETENTION_DAYS=90

# Application Settings
FLASK_ENV=production
FLASK_DEBUG=False
```

4. **Run the application**:

**Development:**
```bash
python app.py
```

**Production (with Gunicorn):**
```bash
gunicorn --config gunicorn_config.py app:app
```

**Docker (recommended for production):**
```bash
docker-compose up -d
```

The application will:
- Automatically create the database if it doesn't exist
- Initialize all tables with proper schema
- Create default admin user (username: `Admin`, password: `admin123`)
- Start patient ID sequence at configured starting ID
- Import ICD-10 codes from Excel files if available

5. **Access the application**:
- **Development:** http://localhost:5000
- **Docker/Production:** http://localhost:8088 (via Nginx)
- Login with: `Admin` / `admin123`
- **Important:** Change the default password immediately after first login

## 🔐 Security Features

### Data Protection
- **Separate sensitive and statistical tables**: PII is isolated from analysis data
- **Password hashing**: Bcrypt with salt
- **Session-based authentication**: Secure user sessions
- **Role-based access control**: Administrator and Staff roles
- **Person hashing**: SHA-256 hashing of MBO for anonymous patient tracking
- **Export access control**: 
  - Administrators: Can export both sensitive (with names/MBO) and anonymized data
  - Staff: Can only export anonymized data (enforced server-side)
- **Security headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS

### Data Validation
- **Real-time patient ID validation**: Prevents duplicate entries with concurrent user support
- **Comprehensive form validation**: All fields validated client-side and server-side
- **Date validation**: Ensures logical date ranges
- **MBO format validation**: 9-digit format enforcement
- **Foreign key constraints**: Data integrity across all tables

## 👥 User Roles

### Administrator
- Full system access
- Manage reference data (ICD-10 codes, medications, surgeries)
- Bulk import/export capabilities
- User management (create, edit, delete users)
- Export sensitive data (includes patient names and MBO)
- Export anonymized data
- Backup and restore operations
- System configuration

### Staff
- Create and edit patient records
- View all patient data
- Data entry and validation
- Search and filter patients
- Export anonymized data only (no access to sensitive exports)

## 📊 Key Features

### 1. Patient Management

#### Patient ID System
- **Auto-increment** starting from configurable ID (default: 01500)
- **5-digit format**: 00001-99999 (leading zeros preserved)
- **Manual override** with real-time duplicate detection
- **Concurrent entry protection** across multiple users
- **API endpoint** for validation before form submission
- **Periodic background checking** to detect ID conflicts

#### Creating New Patients
Comprehensive form with sections:
- **General Data**: ID, name, MBO, sex, dates, eye
- **Main Ocular Conditions**: 40+ specialized fields with hierarchical logic
- **Other Ocular Conditions**: Unlimited ICD-10 coded conditions
- **Previous Surgeries**: Multiple surgery entries with eye specification
- **Systemic Conditions**: ICD-10 coded systemic diseases
- **Medications**: Ocular and systemic medications with timing

#### Editing Existing Patients
- **Advanced search functionality**: Find patients by ID, name, or MBO
- **Filter system**: Filter by conditions, surgeries, medications
- **Pre-filled forms**: All existing data loaded automatically
- **Update tracking**: Changes logged with timestamps
- **Concurrent editing prevention**: Lock mechanism for data integrity

### 2. Hierarchical Form Logic

**Parent-Child Relationships:**
- Select "Phakic" → LOCS III grading fields appear
- Select "Pseudophakic" → IOL type field appears
- Select "Aphakic" → Etiology field appears
- Enable "Glaucoma" → Etiology, OHT/PAC, PXS/PDS fields appear
- Enable "Diabetic Retinopathy" → Stage and substage fields appear
- Enable "Macular Edema" → Etiology field appears
- And many more conditional fields...

**Dynamic Form Behavior:**
- Fields show/hide based on selections
- Default values optimize data entry speed
- Clear visual indication of required fields
- Smooth transitions between states

### 3. Advanced Data Export System

#### Export Options
- **Format**: CSV (Excel-compatible) or XLSX (native Excel with formatting)
- **Data Type** (Administrator only):
  - **Anonymized**: Person hash, no names/MBO
  - **Sensitive**: Includes patient names and MBO
- **Data to Include** (checkboxes):
  - Basic Demographics (always included)
  - Main Ocular Conditions
  - Other Ocular Conditions (ICD-10)
  - Previous Surgeries & Laser Treatments
  - Systemic Conditions
  - Medications (Ocular & Systemic)
- **Date Range**: Optional from/to date filters
- **Advanced Filters**: Filter by specific conditions, surgeries, medications

#### Export Features
- **Binary column format**: Each medication/condition/surgery gets its own column
- **Dynamic columns**: Adapts to patients with varying numbers of conditions/medications
- **Proper column ordering**: Patient info first, then conditions
- **Excel formatting**: Blue headers, bold text, auto-sized columns
- **Generic component extraction**: Individual medication components tracked
- **Audit-friendly filenames**: Includes data type and timestamp

### 4. Bulk Import/Export System

#### ICD-10 Codes Management
- **Bulk Upload**: Import from CSV/XLSX files
- **Column Mapping**: Intelligent auto-detection of code, description, category columns
- **Preview**: Review first 10 rows before importing
- **Category Auto-detection**: Automatically categorizes codes based on prefixes
- **Export**: Download all codes to Excel for editing
- **Update on Conflict**: Updates existing codes if duplicates found

#### Medications Management
- **Bulk Upload**: Import medication lists from Excel/CSV
- **Multi-component Support**: Preserves semicolon-separated generic names
- **Type Detection**: Auto-detects Ocular/Systemic/Both based on keywords
- **Column Mapping**: Flexible mapping of trade name, generic name, type
- **Export**: Download current medication list to Excel

### 5. Backup & Restore System

#### Backup Features
- **Manual Backups**: Create on-demand database backups
- **Scheduled Backups**: Automatic backups (hourly, daily, weekly, monthly)
- **External Drive Support**: Save backups to external drives or network storage
- **Directory Browser**: Navigate server filesystem to select backup location
- **Retention Management**: Automatic deletion of old backups based on retention policy
- **Backup Verification**: Real-time status of backup location and available space

#### Restore Features
- **One-click Restore**: Restore database from any backup file
- **Download Backups**: Download backup files to local machine
- **Backup Management**: View, download, restore, or delete existing backups
- **Safety Confirmations**: Multiple confirmations before restore operations

### 6. Reference Data Management

Administrators can manage all reference data through the Settings interface:

#### ICD-10 Ocular Conditions
- Add, edit, deactivate, or permanently delete codes
- Bulk upload from Excel/CSV files
- Export all codes to Excel
- Search by code or description
- Category organization
- Real-time search filtering

#### ICD-10 Systemic Conditions
- Full CRUD operations
- Bulk import capabilities
- Category support
- Active/inactive status management

#### Medications
- Trade names and generic names
- Medication type (Ocular/Systemic/Both)
- Multi-component medications (semicolon-separated)
- HALMED registry compatible
- Bulk import from Excel/CSV
- Search by trade or generic name

#### Surgical Procedures
- Procedure codes and descriptions
- Predefined categories:
  - Cataract Surgery
  - Glaucoma Surgery
  - Vitreoretinal Surgery
  - Refractive Surgery
  - Corneal Surgery
  - Oculoplastic Surgery
  - Laser Treatment
  - Injection
  - Other (or custom category)

### 7. User Management

#### User Administration
- Create new users (Staff or Administrator)
- Edit user details and roles
- Reset passwords (defaults to: password123)
- Delete users (cannot delete yourself)
- View user statistics and last login

#### User Statistics Display
- Total Users
- Administrators count
- Staff Members count

### 8. Advanced Search & Filtering

#### Patient Search
- Search by Patient ID
- Search by Name
- Search by MBO
- Recent patients list (20 most recent)

#### Advanced Filters
- **Main Ocular Conditions**: Filter by glaucoma, diabetic retinopathy, lens status, macular edema, macular degeneration, epiretinal membrane
- **Other Conditions**: Filter by presence/absence of additional ocular conditions
- **Surgeries**: Filter by surgical history
- **Medications**: Filter by ocular or systemic medications
- **Combination Filters**: Apply multiple filters simultaneously

## 🐳 Docker Deployment

The project includes complete Docker configuration:

### Docker Compose Setup
```yaml
services:
  web:
    - Flask application with Gunicorn
    - Health checks
    - Auto-restart
    - Volume mounts for backups
  
  nginx:
    - Reverse proxy
    - SSL ready (commented configuration included)
    - Port 8088 for HTTP
    - Port 8443 for HTTPS (when configured)
```

### Production Configuration
- **Gunicorn**: Multi-worker setup with auto-restart
- **Nginx**: Reverse proxy with security headers
- **Health Checks**: Automatic service monitoring
- **Persistent Storage**: Volumes for backups and uploads
- **Network Isolation**: Dedicated Docker network

### Deployment
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

## 📊 Database Statistics

A production instance can handle:
- **Patients**: Up to 99,999 (with 5-digit IDs)
- **Conditions per patient**: Unlimited
- **Medications per patient**: Unlimited
- **Surgeries per patient**: Unlimited
- **Concurrent users**: 50+ (with proper PostgreSQL tuning)
- **ICD-10 Codes**: 1000s supported via bulk import
- **Medications**: 1000s supported via bulk import

## 🤝 Best Practices

### Data Entry
1. Always double-check Patient ID before saving
2. Use consistent naming conventions for patients
3. Verify MBO numbers are correct (9 digits)
4. Complete all applicable sections
5. Use "ND" (No Data) when information is unavailable

### Reference Data Management
1. Use bulk import for large datasets (Excel/CSV)
2. Never permanently delete reference data (use Deactivate instead)
3. Use clear, descriptive names
4. Organize by categories
5. Keep codes consistent with international standards
6. Export before making major changes

### User Management
1. Change default passwords immediately
2. Use strong passwords (min 8 chars, mixed case, numbers, symbols)
3. Regularly review user access levels
4. Remove inactive users promptly

### Data Export
1. Use filters to export specific patient cohorts
2. Use anonymized exports for statistical analysis
3. Only export sensitive data when necessary
4. Secure exported files appropriately
5. Delete exported files after use
6. Document export parameters for reproducibility

### Backup & Restore
1. Schedule automatic backups (daily recommended)
2. Store backups on external drives or network storage
3. Test restore procedures periodically
4. Keep multiple backup versions (retention policy)
5. Always create a backup before major changes
6. Verify backup location has sufficient space

## 🧪 Development

### Adding New Condition Fields

1. **Database**: Add column to `ocular_conditions` table
```sql
ALTER TABLE ocular_conditions 
ADD COLUMN new_condition VARCHAR(50);
```

2. **Form** (new_patient.html / edit_patient.html): Add form field
```html
<div class="form-group">
    <label for="new_condition">New Condition</label>
    <select id="new_condition" name="new_condition">
        <option value="0">No</option>
        <option value="1">Yes</option>
    </select>
</div>
```

3. **JavaScript**: Add conditional display logic if hierarchical
```javascript
document.getElementById('new_condition').addEventListener('change', function() {
    // Show/hide related fields
});
```

4. **Backend** (app.py): Update form processing
```python
new_condition = request.form.get('new_condition')
# Include in INSERT/UPDATE query
```

### Database Migrations

For schema changes:
```sql
-- Add column
ALTER TABLE table_name ADD COLUMN column_name TYPE;

-- Modify column
ALTER TABLE table_name ALTER COLUMN column_name TYPE new_type;

-- Add constraint
ALTER TABLE table_name ADD CONSTRAINT constraint_name ...;
```

### Testing

```bash
# Run with debug mode
export FLASK_ENV=development
python app.py

# Check logs for errors
tail -f app.log

# Test with multiple concurrent users
# Open multiple browser sessions
```

## 📁 Configuration

### Environment Variables (.env)

```env
# Database Configuration
DB_NAME=raman_research_prod
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Application Configuration
SECRET_KEY=your-random-secret-key-min-32-chars
FLASK_ENV=production

# Patient ID Configuration
STARTING_PATIENT_ID=1500

# Backup Configuration
BACKUP_DIR=/mnt/medical_backups/raman_backups
BACKUP_RETENTION_DAYS=90

# Optional: For development
DEBUG=False
```

### Database Configuration

**Minimum Requirements:**
- PostgreSQL 15+
- 500MB storage (more for large datasets)
- UTF-8 encoding

**Recommended Settings:**
```postgresql.conf
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
```

## 🔧 Troubleshooting

### Common Issues

**1. Database Connection Error**
```
Error: could not connect to server
```
**Solution:** Check PostgreSQL is running and .env credentials are correct
```bash
sudo systemctl status postgresql
psql -U postgres -d raman_research_prod
```

**2. Patient ID Already Exists**
```
Error: Patient ID already exists
```
**Solution:** Use auto-generated ID or choose a different manual ID

**3. Export Returns Empty File**
```
Export file has no data
```
**Solution:** 
- Check date range filters
- Verify patients exist in selected date range
- Ensure at least one data type checkbox is selected

**4. Cannot Install Dependencies**
```
Error: Failed building wheel for psycopg2
```
**Solution:** 
```bash
# Install PostgreSQL development headers
sudo apt-get install libpq-dev python3-dev

# Or use binary package
pip install psycopg2-binary
```

**5. Backup Directory Not Writable**
```
Error: Permission denied
```
**Solution:**
```bash
# Create directory with proper permissions
sudo mkdir -p /mnt/medical_backups/raman_backups
sudo chown $USER:$USER /mnt/medical_backups/raman_backups
```

**6. Form Fields Not Showing/Hiding**
```
Conditional fields don't appear
```
**Solution:** 
- Check browser console for JavaScript errors
- Verify JavaScript is enabled
- Clear browser cache

## 📄 License

Private medical research project. All rights reserved.

## 📞 Support

For technical issues:
1. Check database connectivity
2. Verify .env configuration
3. Review application logs
4. Check PostgreSQL logs
5. Ensure all dependencies are installed
6. Verify user has appropriate role/permissions

---

**Version:** 1.0  
**Last Updated:** December 2025  
**Status:** Production Ready  
**Database Schema Version:** 1.0