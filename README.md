# Raman Medical Research Database

A comprehensive medical research database system for ophthalmic clinical data collection and analysis.

## 🎯 Project Overview

Raman is a professional medical research database designed specifically for collecting and analyzing ophthalmic (eye-related) clinical data. The system features:

- **Dual-table architecture** for data security (sensitive vs. statistical data)
- **Automatic patient ID generation** starting from 1500 with manual override capability
- **Comprehensive ocular condition tracking** with 40+ specialized fields
- **SHA-256 person hashing** for anonymized data analysis
- **Multi-user support** with role-based access control
- **ICD-10 coding** for conditions and medications
- **Flexible export system** with CSV and Excel formats
- **Complete reference data management** for codes, medications, and surgeries
- **Advanced form validation** with real-time feedback

## 📋 Database Architecture

### Core Tables

#### 1. **users**
Authentication and authorization
- `user_id`, `username`, `password_hash`, `email`, `role`, `created_at`, `last_login`
- Roles: **Administrator**, **Staff** (Patient role removed)

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

#### 11. **icd10_systemic_conditions**
Systemic ICD-10 codes
- `id`, `code`, `description`, `category`, `active`

#### 12. **medications**
HALMED medication registry
- `id`, `trade_name`, `generic_name`, `medication_type` (Ocular/Systemic/Both), `active`

#### 13. **surgeries**
Ocular surgical procedures
- `id`, `surgery_code`, `description`, `category`, `active`

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
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── new_patient.html
│   ├── edit_patient.html
│   ├── validate_data.html
│   ├── export_data.html
│   ├── settings.html
│   ├── settings_icd10_ocular.html
│   ├── settings_icd10_systemic.html
│   ├── settings_medications.html
│   ├── settings_surgeries.html
│   └── user_management.html
└── README.md
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

Required packages:
```
Flask==3.0.0
Flask-Bcrypt==1.0.1
psycopg2-binary==2.9.9
python-dotenv==1.0.0
openpyxl==3.1.2
```

3. **Configure database** (create `.env` file):
```env
# Database Configuration
DB_NAME=raman_research
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432

# Flask Secret Key (change this to a random string in production)
SECRET_KEY=change-this-to-a-random-secret-key # openssl rand -base64 32

# Patient ID Configuration
# Starting patient ID for auto-assignment
# This should be set to approximately where your existing data is (if any)
# Default: 1500
STARTING_PATIENT_ID=1500

# Application Settings
FLASK_ENV=production
FLASK_DEBUG=False
```

4. **Run the application**:
```bash
python app.py
```

The application will:
- Automatically create the database if it doesn't exist
- Initialize all tables with proper schema
- Create default admin user (username: `Admin`, password: `admin123`)
- Start patient ID sequence at 01500

5. **Access the application**:
- Open http://localhost:5000
- Login with: `Admin` / `admin123`
- **Important:** Change the default password immediately after first login

## 🔐 Security Features

### Data Protection
- **Separate sensitive and statistical tables**: PII is isolated from analysis data
- **Password hashing**: Bcrypt with salt
- **Session-based authentication**: Secure user sessions
- **Role-based access control**: Administrator and Staff roles
- **Person hashing**: SHA-256 hashing of MBO for anonymous patient tracking across entries
- **Export access control**: 
  - Administrators: Can export both sensitive (with names/MBO) and anonymized data
  - Staff: Can only export anonymized data (enforced server-side)

### Data Validation
- **Real-time patient ID validation**: Prevents duplicate entries
- **Comprehensive form validation**: All fields validated client-side and server-side
- **Date validation**: Ensures logical date ranges
- **MBO format validation**: 9-digit format enforcement
- **Foreign key constraints**: Data integrity across all tables

## 👥 User Roles

### Administrator
- Full system access
- Manage reference data (ICD-10 codes, medications, surgeries)
- User management (create, edit, delete users)
- Export sensitive data (includes patient names and MBO)
- Export anonymized data
- System configuration

### Staff
- Create and edit patient records
- View all patient data
- Data entry and validation
- Export anonymized data only (no access to sensitive exports)

## 📊 Key Features

### 1. Patient Management

#### Patient ID System
- **Auto-increment** starting from 01500
- **5-digit format**: 00001-99999 (leading zeros preserved)
- **Manual override** with real-time duplicate detection
- **Concurrent entry protection** across multiple users
- **API endpoint** for validation before form submission

#### Creating New Patients
Comprehensive form with sections:
- **General Data**: ID, name, MBO, sex, dates, eye
- **Main Ocular Conditions**: 40+ specialized fields with hierarchical logic
- **Other Ocular Conditions**: Unlimited ICD-10 coded conditions
- **Previous Surgeries**: Multiple surgery entries with eye specification
- **Systemic Conditions**: ICD-10 coded systemic diseases
- **Medications**: Ocular and systemic medications with timing

#### Editing Existing Patients
- **Search functionality**: Find patients by ID or name
- **Pre-filled forms**: All existing data loaded automatically
- **Update tracking**: Changes logged
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

### 3. Data Export System

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

#### Export Features
- **Role-based access**: Staff can only export anonymized data (enforced server-side)
- **Dynamic columns**: Adapts to patients with varying numbers of conditions/medications
- **Proper column ordering**: Patient info first, then conditions (matches form layout)
- **Excel formatting**: Blue headers, bold text, auto-sized columns
- **Audit-friendly filenames**: Includes data type and timestamp

#### Export Column Order (Sensitive)
```
A: patient_id
B: patient_name
C: mbo
D: sex
E: date_of_birth
F: date_of_sample_collection
G: eye
H: person_hash
I: age
J+: Main ocular conditions (if selected)
Then: Dynamic columns (other conditions, surgeries, medications)
```

#### Export Column Order (Anonymized)
```
A: patient_id
B: person_hash
C: sex
D: eye
E: age
F+: Main ocular conditions (if selected)
Then: Dynamic columns (other conditions, surgeries, medications)
```

### 4. Reference Data Management

Administrators can manage all reference data through the Settings interface:

#### ICD-10 Ocular Conditions
- Add, edit, deactivate codes
- Search by code or description
- Category organization
- Real-time search filtering

#### ICD-10 Systemic Conditions
- Full CRUD operations
- Category support
- Active/inactive status management

#### Medications
- Trade names and generic names
- Medication type (Ocular/Systemic/Both)
- HALMED registry compatible
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

### 5. User Management

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

## 📝 Complete Workflows

### Workflow 1: Adding a New Patient

1. **Login** → Dashboard → Click **"New Patient"**

2. **General Data Section**:
   - Patient ID: Auto-filled with next ID (e.g., 01523), editable
   - Patient Name: Full name
   - MBO: 9-digit number (format: 123456789)
   - Sex: Male/Female
   - Date of Birth: Calendar picker
   - Date of Sample Collection: Calendar picker
   - Eye: L (Left), R (Right), or ND (No Data)

3. **Main Ocular Conditions**:
   
   **Lens Status & Cataract:**
   - Select: Phakic, Pseudophakic, or Aphakic
   - If Phakic → Enter LOCS III grades (NO, NC, C, P)
   - If Pseudophakic → Select IOL type
   - If Aphakic → Select etiology

   **Glaucoma:**
   - Enable if present
   - If yes → Select etiology, mark OHT/PAC if applicable
   - Mark steroid responder if applicable
   - Mark PXS or PDS if present

   **Diabetic Retinopathy:**
   - Enable if present
   - Select stage: NPDR or PDR
   - If NPDR → Select severity (Mild/Moderate/Severe)
   - If PDR → Select status (Active/Stable/Regressed)

   **Macular Edema:**
   - Enable if present
   - Select etiology

   **Macular Degeneration/Dystrophy:**
   - Enable if present
   - Select type and etiology
   - If AMD → Select dry/wet, stage, exudation status
   - If Other → Select stage, exudation status

   **Macular Hole/VMT:**
   - Enable if present
   - Select etiology (Idiopathic/Traumatic/Secondary)
   - If secondary → Specify cause
   - Select treatment status

   **Epiretinal Membrane:**
   - Enable if present
   - Select etiology
   - If secondary → Specify cause
   - Select treatment status

   **Retinal Detachment:**
   - Enable if present
   - Select etiology
   - Select treatment status
   - Mark PVR if present

   **Vitreous Hemorrhage/Opacification:**
   - Enable if present
   - Select etiology

4. **Other Ocular Conditions** (Repeatable):
   - Click **"+ Add Other Ocular Condition"**
   - Select ICD-10 code from dropdown
   - Select eye (R/L/R+L/ND)
   - Add more as needed
   - Remove with (−) button

5. **Previous Ocular Surgeries** (Repeatable):
   - Click **"+ Add Surgery"**
   - Select surgery from dropdown
   - Select eye
   - Add more as needed
   - Remove with (−) button

6. **Systemic Conditions** (Repeatable):
   - Click **"+ Add Systemic Condition"**
   - Select ICD-10 code
   - Add more as needed
   - Remove with (−) button

7. **Ocular Medications** (Repeatable):
   - Click **"+ Add Ocular Medication"**
   - Select medication (trade name)
   - Generic name auto-fills
   - Enter days since last application
   - Select eye
   - Add more as needed
   - Remove with (−) button

8. **Systemic Medications** (Repeatable):
   - Click **"+ Add Systemic Medication"**
   - Select medication
   - Generic name auto-fills
   - Enter days since last application
   - Add more as needed
   - Remove with (−) button

9. **Save** → All data distributed across appropriate tables

### Workflow 2: Validating/Editing Existing Data

1. **Dashboard** → Click **"Validate Data"**

2. **Search Options**:
   - Search by Patient ID (exact match)
   - Search by Patient Name (partial match)
   - Recent patients list

3. **Select Patient** → Click patient row

4. **Edit Form Opens**:
   - All fields pre-filled with existing data
   - All repeatable sections show existing entries
   - Modify any field as needed

5. **Save Updates** → Changes committed to database

### Workflow 3: Exporting Data

1. **Dashboard** → Click **"Export Data"**

2. **View Statistics**:
   - Total Patients count
   - Gender distribution (Male/Female)
   - Age distribution chart

3. **Configure Export**:
   
   **Export Format:**
   - CSV (Excel Compatible) - for analysis software
   - Excel (.xlsx) - formatted with headers

   **Data Privacy Level** (Administrator only):
   - Anonymized (Person Hash, no names/MBO)
   - Sensitive (Includes Patient Names & MBO)

   **Data to Include:**
   - ☑ Basic Demographics (always included)
   - ☐ Main Ocular Conditions
   - ☐ Other Ocular Conditions (ICD-10)
   - ☐ Previous Surgeries & Laser Treatments
   - ☐ Systemic Conditions
   - ☐ Medications (Ocular & Systemic)

   **Date Range** (Optional):
   - From Date: Start of range
   - To Date: End of range

4. **Click "Export Data"** → File downloads automatically

5. **Open in Excel/LibreOffice**:
   - CSV: Plain format, universal compatibility
   - XLSX: Formatted headers, professional appearance

### Workflow 4: Managing Reference Data (Administrator)

1. **Dashboard** → Click **"Settings"**

2. **Select Reference Type**:
   - ICD-10 Ocular Conditions
   - ICD-10 Systemic Conditions
   - Medications
   - Surgical Procedures

3. **For Any Reference Type**:
   
   **Add New Entry:**
   - Click **"+ Add New [Type]"**
   - Enter code/name
   - Enter description
   - Select/enter category (optional)
   - Click "Create"

   **Edit Existing:**
   - Click **"Edit"** on any row
   - Modify description or category
   - Code/name is read-only
   - Click "Update"

   **Deactivate/Activate:**
   - Click **"Deactivate"** to hide from dropdowns
   - Click **"Activate"** to restore
   - Never deletes (preserves existing patient data references)

   **Search:**
   - Type in search bar
   - Real-time filtering by code or description

### Workflow 5: Managing Users (Administrator)

1. **Dashboard** → Click **"Settings"** → Click **"User Management"**

2. **View User Statistics**:
   - Total Users
   - Administrators count
   - Staff Members count

3. **Create New User**:
   - Click **"+ Add New User"**
   - Enter username
   - Enter email (optional)
   - Enter password (min 6 characters)
   - Select role: Staff or Administrator
   - Click "Create User"

4. **Edit Existing User**:
   - Click **"Edit"** on user row
   - Modify username, email, or role
   - Optionally enter new password
   - Click "Update User"

5. **Reset Password**:
   - Click **"Reset Password"**
   - Confirm action
   - Password reset to: password123
   - User should change on next login

6. **Delete User**:
   - Click **"Delete"** (not available for your own account)
   - Confirm action
   - User permanently removed

## 🗂️ Reference Data Format

### ICD-10 Codes (Both Ocular and Systemic)
```
Code: H35.31
Description: Nonexudative age-related macular degeneration
Category: Retina
Status: Active
```

### Medications
```
Trade Name: Cosopt
Generic Name: Dorzolamide/Timolol
Type: Ocular
Status: Active
```

### Surgeries
```
Code: Phaco+IOL
Description: Phacoemulsification with intraocular lens implantation
Category: Cataract Surgery
Status: Active
```

## 📈 Implementation Status

### ✅ Completed Features

**Core Functionality:**
- ✅ Complete database schema with all tables
- ✅ User authentication system
- ✅ Role-based access control (Administrator, Staff)
- ✅ Dashboard with all main actions

**Patient Management:**
- ✅ Patient ID generation and validation
- ✅ Complete new patient form with all 40+ ocular condition fields
- ✅ Dynamic form field showing/hiding based on selections
- ✅ Multiple entry addition for conditions, surgeries, medications
- ✅ Patient search and editing interface
- ✅ Concurrent editing prevention

**Data Export:**
- ✅ CSV export functionality
- ✅ Excel (XLSX) export with formatting
- ✅ Role-based export access (sensitive vs anonymized)
- ✅ Flexible data filtering (date range, data types)
- ✅ Dynamic column generation for variable-length data
- ✅ Proper column ordering matching form layout

**Reference Data Management:**
- ✅ ICD-10 Ocular Conditions management
- ✅ ICD-10 Systemic Conditions management
- ✅ Medications management
- ✅ Surgical Procedures management
- ✅ Add/Edit/Deactivate functionality
- ✅ Real-time search and filtering

**User Management:**
- ✅ User creation and editing
- ✅ Password reset functionality
- ✅ User deletion with protection
- ✅ Role assignment
- ✅ User statistics display

**Security & Validation:**
- ✅ Password hashing (Bcrypt)
- ✅ Session management
- ✅ Real-time form validation
- ✅ Duplicate patient ID prevention
- ✅ Server-side export access control

### 🔮 Possible Future Enhancements

**Analytics & Reporting:**
- Advanced statistical analysis tools
- Custom report generation
- Data visualization dashboards
- Trend analysis over time

**Integration:**
- Integration with lab systems
- HL7/FHIR compliance
- Electronic health record (EHR) integration
- Automated data import from other systems

**User Experience:**
- Mobile application for data entry
- Offline mode with synchronization
- Batch patient import
- Template-based data entry

**Advanced Features:**
- Machine learning predictions
- Automated quality checks
- Multi-language support
- Advanced search with filters
- Patient data versioning/history
- Audit logging with detailed trails

**Security & Compliance:**
- Two-factor authentication
- Data encryption at rest
- HTTPS/TLS enforcement
- HIPAA compliance tools
- GDPR compliance features
- Session timeout management
- IP allowlisting

**Collaboration:**
- Real-time collaboration features
- Comments and annotations
- Data review workflow
- Approval processes

## 🛠️ Technical Stack

**Backend:**
- Python 3.9+
- Flask 3.0 (Web framework)
- Flask-Bcrypt (Password hashing)
- psycopg2 (PostgreSQL adapter)

**Database:**
- PostgreSQL 15+
- Complex relational schema
- Foreign key constraints
- Automatic timestamp tracking

**Frontend:**
- HTML5
- CSS3 (Custom styling, no frameworks)
- Vanilla JavaScript (No jQuery or frameworks)
- Responsive design

**Export:**
- openpyxl (Excel generation)
- CSV module (Python standard library)

## 🐳 Docker Deployment

Docker configuration available for:
- PostgreSQL container
- Flask application container
- Nginx reverse proxy
- Persistent data volumes
- Network configuration

See `docker-compose.yml` for complete setup.

## 🔧 Development

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

## 📝 Configuration

### Environment Variables (.env)

```env
# Database Configuration
DB_NAME=raman_research
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Application Configuration
SECRET_KEY=your-random-secret-key-min-32-chars
FLASK_ENV=production

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

## 🔍 Troubleshooting

### Common Issues

**1. Database Connection Error**
```
Error: could not connect to server
```
**Solution:** Check PostgreSQL is running and .env credentials are correct
```bash
sudo systemctl status postgresql
psql -U postgres -d raman_research
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

**4. Cannot Install openpyxl**
```
Error: Failed building wheel for openpyxl
```
**Solution:** 
```bash
pip install --upgrade pip
pip install openpyxl --no-cache-dir
```

**5. Form Fields Not Showing/Hiding**
```
Conditional fields don't appear
```
**Solution:** 
- Check browser console for JavaScript errors
- Verify JavaScript is enabled
- Clear browser cache

## 📊 Database Statistics

A production instance can handle:
- **Patients**: Theoretically up to 99,999 (with 5-digit IDs)
- **Conditions per patient**: Unlimited
- **Medications per patient**: Unlimited
- **Surgeries per patient**: Unlimited
- **Concurrent users**: 50+ (with proper PostgreSQL tuning)

## 🤝 Best Practices

### Data Entry
1. Always double-check Patient ID before saving
2. Use consistent naming conventions for patients
3. Verify MBO numbers are correct (9 digits)
4. Complete all applicable sections
5. Use "ND" (No Data) when information is unavailable

### Reference Data Management
1. Never delete reference data (use Deactivate instead)
2. Use clear, descriptive names
3. Organize by categories
4. Keep codes consistent with international standards

### User Management
1. Change default passwords immediately
2. Use strong passwords (min 8 chars, mixed case, numbers, symbols)
3. Regularly review user access levels
4. Remove inactive users promptly

### Data Export
1. Use anonymized exports for statistical analysis
2. Only export sensitive data when necessary
3. Secure exported files appropriately
4. Delete exported files after use
5. Document export parameters for reproducibility

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

## 🎓 Training Resources

### For Administrators
- User management guide
- Reference data import procedures
- Export configuration best practices
- Database backup and maintenance

### For Staff
- Patient data entry tutorial
- Form field descriptions
- Search and edit procedures
- Export functionality guide

---

**Version:** 1.0  
**Last Updated:** November 2025  
**Status:** Production Ready  
**Database Schema Version:** 1.0