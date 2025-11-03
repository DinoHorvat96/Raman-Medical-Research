# Raman Medical Research Database

A comprehensive medical research database system for ophthalmic clinical data collection and analysis.

## 🎯 Project Overview

Raman is a professional medical research database designed specifically for collecting and analyzing ophthalmic (eye-related) clinical data. The system features:

- **Dual-table architecture** for data security (sensitive vs. statistical data)
- **Automatic patient ID generation** starting from 1500 with manual override capability
- **Hierarchical condition tracking** with complex parent-child relationships
- **SHA-256 person hashing** for anonymized data analysis
- **Multi-user support** with concurrent data entry prevention
- **ICD-10 coding** for conditions and medications
- **Flexible export** for statistical analysis

## 📋 Database Architecture

### Core Tables

#### 1. **users**
Authentication and authorization
- `user_id`, `username`, `password_hash`, `email`, `role`, `created_at`, `last_login`

#### 2. **patients_sensitive** (Protected Data)
Personal identifiable information
- `patient_id` (1-99999, custom or auto-generated)
- `patient_name`, `mbo` (9 digits), `date_of_birth`, `date_of_sample_collection`

#### 3. **patients_statistical** (Anonymized Export Data)
De-identified data for analysis
- `patient_id`, `person_hash` (SHA-256 of MBO), `age` (calculated), `sex`, `eye`

#### 4. **ocular_conditions**
Main ocular conditions (one row per patient)
- Lens status (Phakic/Pseudophakic/Aphakic) with LOCS III grading
- IOL type and aphakia etiology
- Glaucoma (with etiology, OHT, PAC subtypes)
- Diabetic retinopathy (NPDR/PDR stages)
- Macular edema, AMD, macular holes, ERM
- Retinal detachment, vitreous hemorrhage
- 40+ specialized ophthalmic fields

#### 5. **other_ocular_conditions** (One-to-Many)
Additional ICD-10 coded ocular conditions
- `patient_id`, `icd10_code`, `eye`

#### 6. **previous_ocular_surgeries** (One-to-Many)
Surgical history
- `patient_id`, `surgery_code`, `eye`

#### 7. **systemic_conditions** (One-to-Many)
Non-ocular ICD-10 conditions
- `patient_id`, `icd10_code`

#### 8. **ocular_medications** (One-to-Many)
Eye medications with timing
- `patient_id`, `trade_name`, `generic_name`, `eye`, `days_before_collection`

#### 9. **systemic_medications** (One-to-Many)
Systemic medications
- `patient_id`, `trade_name`, `generic_name`, `days_before_collection`

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 13+
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
│   └── new_patient.html
└── README.md
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure database** (create `.env` file):
```env
DB_NAME=raman_research
DB_USER=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=your-random-secret-key
```

4. **Run the application**:
```bash
python app.py
```

The application will:
- Automatically create the database if it doesn't exist
- Initialize all tables with proper schema
- Create default admin user (Admin/admin123)
- Start patient ID sequence at 1500

5. **Access the application**:
- Open http://localhost:5000
- Login with: `Admin` / `admin123`

## 🔐 Security Features

### Data Protection
- **Separate sensitive and statistical tables**: PII is isolated from analysis data
- **Password hashing**: Bcrypt with salt
- **Session-based authentication**: Secure user sessions
- **Role-based access control**: Admin, Staff, Patient roles
- **Person hashing**: SHA-256 hashing of MBO for anonymous patient tracking

### Future Security Enhancements
- HTTPS/TLS encryption
- CSRF protection
- Audit logging
- Data encryption at rest
- Two-factor authentication
- Session timeouts
- HIPAA/GDPR compliance measures

## 👥 User Roles

### Administrator
- Full system access
- Import reference lists (ICD-10 codes, medications, surgeries)
- User management
- System configuration
- Data export and validation

### Staff
- Create and edit patient records
- View all patient data
- Data entry and validation
- Export data for analysis

### Patient
- View own medical records (future feature)
- Limited read-only access

## 📊 Key Features

### Patient ID Management
- **Auto-increment** starting from 1500 (configurable)
- **Manual override** with duplicate detection
- **Real-time validation** via API endpoint
- **Concurrent entry protection** across multiple users

### Hierarchical Condition Forms
- **Parent-child relationships**: Main conditions reveal sub-conditions
- **Dynamic form fields**: Fields appear/hide based on selections
- **Default values**: Most common values pre-selected (typically 0 or ND)
- **Validation**: Ensure data consistency

### Multiple Related Records
- **Unlimited entries**: Conditions, surgeries, medications
- **Dynamic addition**: Add more entries via (+) button
- **Individual tracking**: Each entry stored separately

### Data Export
Statistical export table automatically includes:
- De-identified patient data (person_hash instead of name/MBO)
- Calculated age at sample collection
- All ocular and systemic conditions
- Medication history with timing
- Surgical history

## 🔄 Workflow

### Adding a New Patient

1. **Dashboard** → Click "New Patient"
2. **General Data**:
   - Patient ID auto-populated (editable)
   - Enter name, MBO, sex
   - Enter dates (DOB, sample collection)
   - Select eye (L/R/ND)

3. **Main Ocular Conditions**:
   - Select lens status → Sub-fields appear
   - Complete LOCS III grading (if Phakic)
   - Fill glaucoma details (if applicable)
   - Document retinopathy, AMD, etc.

4. **Additional Conditions** (repeatable):
   - Add ICD-10 coded conditions
   - Specify affected eye
   - Click (+) to add more

5. **Previous Surgeries** (repeatable):
   - Select from surgery list
   - Specify eye
   - Add multiple entries

6. **Medications** (repeatable):
   - Select from medication list
   - Enter days before collection
   - Specify eye (for ocular meds)

7. **Save** → Data distributed across multiple tables

### Validating/Editing Existing Data

1. **Dashboard** → Click "Validate Data"
2. Search for patient by ID or name
3. Edit form (same as New Patient)
4. All existing data pre-filled
5. Save updates

### Exporting Data

1. **Dashboard** → Click "Export Data"
2. Select date range, conditions, or custom filters
3. Choose export format (CSV, Excel)
4. Statistical table exported (anonymized)

## 🗂️ ICD-10 and Reference Lists

### Importing Reference Lists
Administrators can import:
- **ICD-10 codes**: Ocular and systemic conditions
- **Medication lists**: HALMED registry (trade names + generics)
- **Surgery codes**: Standard ophthalmic procedures

### Data Structure
Reference lists stored with:
- Code/ID
- Description
- Category
- Active status

Updates to reference lists don't affect existing patient data.

## 📈 Current Implementation Status

### ✅ Completed
- Database schema with all tables
- User authentication system
- Dashboard with main actions
- Patient ID generation and validation
- Basic new patient form
- Security measures (password hashing, sessions)

### 🚧 In Progress
- Complete new patient form (all condition fields)
- Dynamic form field showing/hiding
- Multiple entry addition (+) buttons
- Reference list management

### 📋 Planned
- Patient search and editing
- Data validation interface
- Export functionality
- Reference list import
- Advanced filtering and reporting
- User management interface

## 🛠️ Technical Stack

- **Backend**: Python 3.9+, Flask 3.0
- **Database**: PostgreSQL 15+
- **Authentication**: Flask-Bcrypt
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Deployment**: Docker, Nginx

## 🐳 Docker Deployment

See `docker-compose.yml` for complete setup with:
- PostgreSQL container
- Flask application container
- Nginx reverse proxy
- Persistent data volumes

## 📝 Development Notes

### Adding New Condition Fields

1. Add column to `ocular_conditions` table
2. Add form field in `new_patient.html`
3. Add JavaScript for conditional display (if hierarchical)
4. Update form processing in `app.py`

### Database Migrations

For schema changes:
```sql
-- Example: Add new column
ALTER TABLE ocular_conditions 
ADD COLUMN new_field VARCHAR(50);
```

### Testing
```bash
# Run with debug mode
python app.py

# Check logs for errors
# Test with multiple concurrent users
```

## 🤝 Contributing

This is a private medical research project. Contributions should follow:
1. Medical data handling best practices
2. HIPAA/GDPR compliance guidelines
3. Code review process
4. Testing requirements

## 📄 License

Private medical research project. All rights reserved.

## 🆘 Support

For technical issues:
1. Check database connection
2. Verify .env configuration
3. Review application logs
4. Check PostgreSQL logs

## 🔮 Future Enhancements

- Mobile application for data entry
- Real-time collaboration features
- Advanced statistical analysis tools
- Integration with lab systems
- Automated report generation
- Machine learning predictions
- Multi-language support
- Cloud deployment options