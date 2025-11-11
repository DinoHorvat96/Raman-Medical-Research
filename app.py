from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_bcrypt import Bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import os
import hashlib
from datetime import datetime, date
from functools import wraps
import io
import csv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
bcrypt = Bcrypt(app)

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'raman_research_prod'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}

# Configuration for starting Patient ID
STARTING_PATIENT_ID = int(os.getenv('STARTING_PATIENT_ID', '1500'))


def create_database_if_not_exists():
    """Create the database if it doesn't exist"""
    try:
        print(f"Checking if database '{DB_CONFIG['dbname']}' exists...")
        print(f"Connecting to PostgreSQL server at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"Using user: {DB_CONFIG['user']}")

        # Connect to postgres database to check/create the database
        conn = psycopg2.connect(
            dbname='postgres',
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG['dbname'],))
        exists = cur.fetchone()

        if not exists:
            print(f"Database '{DB_CONFIG['dbname']}' does not exist. Creating...")
            cur.execute(f"CREATE DATABASE {DB_CONFIG['dbname']}")
            print(f"✓ Database '{DB_CONFIG['dbname']}' created successfully")
        else:
            print(f"✓ Database '{DB_CONFIG['dbname']}' already exists")

        cur.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"✗ Error with database: {e}")
        print(f"\nPlease ensure PostgreSQL is running and create the database manually:")
        print(f"  CREATE DATABASE {DB_CONFIG['dbname']};")
        return False


def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


def init_database():
    """Initialize database with all required tables"""
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False

    try:
        cur = conn.cursor()

        print("Creating tables...")

        # Create users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(100),
                role VARCHAR(20) NOT NULL CHECK (role IN ('Administrator', 'Staff', 'Patient')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')

        # Create patients_sensitive table (PII data)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS patients_sensitive (
                patient_id INTEGER PRIMARY KEY CHECK (patient_id >= 1 AND patient_id <= 99999),
                patient_name VARCHAR(255) NOT NULL,
                mbo VARCHAR(9) NOT NULL,
                date_of_birth DATE,
                date_of_sample_collection DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create patients_statistical table (anonymized data)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS patients_statistical (
                patient_id INTEGER PRIMARY KEY REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                person_hash VARCHAR(64) NOT NULL,
                age INTEGER,
                sex VARCHAR(1) CHECK (sex IN ('M', 'F')),
                eye VARCHAR(3) CHECK (eye IN ('L', 'R', 'ND')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create ocular_conditions table (main conditions - one row per patient)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS ocular_conditions (
                patient_id INTEGER PRIMARY KEY REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                lens_status VARCHAR(20) CHECK (lens_status IN ('Phakic', 'Pseudophakic', 'Aphakic', 'ND')),
                locs_iii_no VARCHAR(10),
                locs_iii_nc VARCHAR(10),
                locs_iii_c VARCHAR(10),
                locs_iii_p VARCHAR(10),
                iol_type VARCHAR(50),
                etiology_aphakia VARCHAR(50),
                glaucoma VARCHAR(10),
                oht_or_pac VARCHAR(10),
                etiology_glaucoma VARCHAR(50),
                steroid_responder VARCHAR(10),
                pxs VARCHAR(10),
                pds VARCHAR(10),
                diabetic_retinopathy VARCHAR(10),
                stage_diabetic_retinopathy VARCHAR(50),
                stage_npdr VARCHAR(50),
                stage_pdr VARCHAR(50),
                macular_edema VARCHAR(10),
                etiology_macular_edema VARCHAR(50),
                macular_degeneration_dystrophy VARCHAR(10),
                etiology_macular_deg_dyst VARCHAR(50),
                stage_amd VARCHAR(50),
                exudation_amd VARCHAR(10),
                stage_other_macular_deg VARCHAR(50),
                exudation_other_macular_deg VARCHAR(10),
                macular_hole_vmt VARCHAR(10),
                etiology_mh_vmt VARCHAR(50),
                cause_secondary_mh_vmt TEXT,
                treatment_status_mh_vmt VARCHAR(50),
                epiretinal_membrane VARCHAR(10),
                etiology_erm VARCHAR(50),
                cause_secondary_erm TEXT,
                treatment_status_erm VARCHAR(50),
                retinal_detachment VARCHAR(50),
                etiology_rd VARCHAR(100),
                treatment_status_rd VARCHAR(100),
                pvr VARCHAR(10),
                vitreous_haemorrhage_opacification VARCHAR(50),
                etiology_vitreous_haemorrhage VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create other_ocular_conditions table (one-to-many)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS other_ocular_conditions (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                icd10_code VARCHAR(20) NOT NULL,
                eye VARCHAR(10) CHECK (eye IN ('R', 'L', 'R+L', 'ND')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create previous_ocular_surgeries table (one-to-many)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS previous_ocular_surgeries (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                surgery_code VARCHAR(100) NOT NULL,
                eye VARCHAR(10) CHECK (eye IN ('R', 'L', 'R+L', 'ND')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create systemic_conditions table (one-to-many)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS systemic_conditions (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                icd10_code VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create ocular_medications table (one-to-many)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS ocular_medications (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                trade_name VARCHAR(255) NOT NULL,
                generic_name VARCHAR(255) NOT NULL,
                eye VARCHAR(10) CHECK (eye IN ('R', 'L', 'R+L', 'ND')),
                last_application_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create systemic_medications table (one-to-many)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS systemic_medications (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                trade_name VARCHAR(255) NOT NULL,
                generic_name VARCHAR(255) NOT NULL,
                last_application_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create reference data tables
        cur.execute('''
            CREATE TABLE IF NOT EXISTS icd10_ocular_conditions (
                id SERIAL PRIMARY KEY,
                code VARCHAR(20) UNIQUE NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(100),
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS icd10_systemic_conditions (
                id SERIAL PRIMARY KEY,
                code VARCHAR(20) UNIQUE NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(100),
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS medications (
                id SERIAL PRIMARY KEY,
                trade_name VARCHAR(255) NOT NULL,
                generic_name VARCHAR(255) NOT NULL,
                medication_type VARCHAR(20) CHECK (medication_type IN ('Ocular', 'Systemic', 'Both')),
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS surgeries (
                id SERIAL PRIMARY KEY,
                code VARCHAR(100) UNIQUE NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(100),
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        print("✓ Tables created successfully")

        # Insert default admin user if no users exist
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            admin_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
            cur.execute('''
                INSERT INTO users (username, password_hash, email, role)
                VALUES (%s, %s, %s, %s)
            ''', ('Admin', admin_password, '', 'Administrator'))
            conn.commit()
            print("✓ Default admin user created (username: Admin, password: admin123)")
            print("  ⚠️  IMPORTANT: Change the admin password after first login!")

        # Check if ICD-10 ocular conditions table is empty
        cur.execute("SELECT COUNT(*) FROM icd10_ocular_conditions")
        if cur.fetchone()[0] == 0:
            # Insert common ocular ICD-10 codes
            ocular_codes = [
                ('H25.9', 'Senile cataract, unspecified', 'Cataract'),
                ('H26.9', 'Cataract, unspecified', 'Cataract'),
                ('H40.1', 'Primary open-angle glaucoma', 'Glaucoma'),
                ('H40.2', 'Primary angle-closure glaucoma', 'Glaucoma'),
                ('H35.3', 'Degeneration of macula and posterior pole', 'Retinal'),
                ('H36.0', 'Diabetic retinopathy', 'Retinal'),
                ('H33.0', 'Retinal detachment with retinal break', 'Retinal'),
                ('H34.8', 'Other retinal vascular occlusions', 'Retinal'),
            ]
            cur.executemany('''
                INSERT INTO icd10_ocular_conditions (code, description, category, active)
                VALUES (%s, %s, %s, TRUE)
            ''', ocular_codes)
            conn.commit()
            print(f"Inserted {len(ocular_codes)} sample ICD-10 ocular codes")

        # Check if ICD-10 systemic conditions table is empty
        cur.execute("SELECT COUNT(*) FROM icd10_systemic_conditions")
        if cur.fetchone()[0] == 0:
            # Insert common systemic ICD-10 codes
            systemic_codes = [
                ('E11.9', 'Type 2 diabetes mellitus without complications', 'Endocrine'),
                ('I10', 'Essential (primary) hypertension', 'Cardiovascular'),
                ('E78.5', 'Hyperlipidemia, unspecified', 'Endocrine'),
            ]
            cur.executemany('''
                INSERT INTO icd10_systemic_conditions (code, description, category, active)
                VALUES (%s, %s, %s, TRUE)
            ''', systemic_codes)
            conn.commit()
            print(f"Inserted {len(systemic_codes)} sample ICD-10 systemic codes")

        # Check if medications table is empty
        cur.execute("SELECT COUNT(*) FROM medications")
        if cur.fetchone()[0] == 0:
            # Insert sample medications
            sample_medications = [
                # Ocular medications
                ('Timolol 0.5%', 'Timolol', 'Ocular'),
                ('Xalatan', 'Latanoprost', 'Ocular'),
                ('Cosopt', 'Dorzolamide/Timolol', 'Ocular'),
                ('Lumigan', 'Bimatoprost', 'Ocular'),
                ('Travatan', 'Travoprost', 'Ocular'),
                ('Azarga', 'Brinzolamide/Timolol', 'Ocular'),
                ('Combigan', 'Brimonidine/Timolol', 'Ocular'),
                ('Alphagan', 'Brimonidine', 'Ocular'),
                ('Pred Forte', 'Prednisolone acetate 1%', 'Ocular'),
                ('Maxidex', 'Dexamethasone', 'Ocular'),
                ('Nevanac', 'Nepafenac', 'Ocular'),
                ('Acular', 'Ketorolac', 'Ocular'),
                ('Voltaren Ophtha', 'Diclofenac', 'Ocular'),
                ('Lucentis', 'Ranibizumab', 'Ocular'),
                ('Eylea', 'Aflibercept', 'Ocular'),
                ('Avastin', 'Bevacizumab', 'Ocular'),
                ('Ozurdex', 'Dexamethasone implant', 'Ocular'),
                ('Iluvien', 'Fluocinolone acetonide implant', 'Ocular'),
                ('Vigamox', 'Moxifloxacin', 'Ocular'),
                ('Ciloxan', 'Ciprofloxacin', 'Ocular'),
                ('TobraDex', 'Tobramycin/Dexamethasone', 'Ocular'),
                ('Systane', 'Artificial tears', 'Ocular'),
                ('Refresh', 'Artificial tears', 'Ocular'),
                ('Hylo-Comod', 'Sodium hyaluronate', 'Ocular'),
                # Systemic medications
                ('Aspirin', 'Acetylsalicylic acid', 'Systemic'),
                ('Metformin', 'Metformin', 'Systemic'),
                ('Glucophage', 'Metformin', 'Systemic'),
                ('Insulin', 'Insulin', 'Systemic'),
                ('Lantus', 'Insulin glargine', 'Systemic'),
                ('NovoRapid', 'Insulin aspart', 'Systemic'),
                ('Atorvastatin', 'Atorvastatin', 'Systemic'),
                ('Lipitor', 'Atorvastatin', 'Systemic'),
                ('Simvastatin', 'Simvastatin', 'Systemic'),
                ('Amlodipine', 'Amlodipine', 'Systemic'),
                ('Norvasc', 'Amlodipine', 'Systemic'),
                ('Lisinopril', 'Lisinopril', 'Systemic'),
                ('Enalapril', 'Enalapril', 'Systemic'),
                ('Losartan', 'Losartan', 'Systemic'),
                ('Cozaar', 'Losartan', 'Systemic'),
                ('Warfarin', 'Warfarin', 'Systemic'),
                ('Coumadin', 'Warfarin', 'Systemic'),
                ('Plavix', 'Clopidogrel', 'Systemic'),
                ('Clopidogrel', 'Clopidogrel', 'Systemic'),
                ('Xarelto', 'Rivaroxaban', 'Systemic'),
                ('Eliquis', 'Apixaban', 'Systemic'),
                ('Levothyroxine', 'Levothyroxine', 'Systemic'),
                ('Synthroid', 'Levothyroxine', 'Systemic'),
                ('Prednisone', 'Prednisone', 'Systemic'),
                ('Methylprednisolone', 'Methylprednisolone', 'Systemic'),
            ]

            cur.executemany('''
                INSERT INTO medications (trade_name, generic_name, medication_type, active)
                VALUES (%s, %s, %s, TRUE)
            ''', sample_medications)
            conn.commit()
            print(f"Inserted {len(sample_medications)} sample medications")

        # Check if surgeries table is empty
        cur.execute("SELECT COUNT(*) FROM surgeries")
        if cur.fetchone()[0] == 0:
            # Insert common ocular surgeries
            surgeries = [
                ('PHACO', 'Phacoemulsification with IOL implantation', 'Cataract Surgery'),
                ('ECCE', 'Extracapsular cataract extraction', 'Cataract Surgery'),
                ('ICCE', 'Intracapsular cataract extraction', 'Cataract Surgery'),
                ('IOL-EXCH', 'IOL exchange', 'Cataract Surgery'),
                ('IOL-REPO', 'IOL repositioning', 'Cataract Surgery'),
                ('SEC-IOL', 'Secondary IOL implantation', 'Cataract Surgery'),
                ('TRAB', 'Trabeculectomy', 'Glaucoma Surgery'),
                ('TRAB-REV', 'Trabeculectomy revision', 'Glaucoma Surgery'),
                ('TUBE', 'Glaucoma drainage device (tube shunt)', 'Glaucoma Surgery'),
                ('CYCLO', 'Cyclophotocoagulation', 'Glaucoma Surgery'),
                ('MIGS', 'Minimally invasive glaucoma surgery', 'Glaucoma Surgery'),
                ('iStent', 'iStent trabecular micro-bypass', 'Glaucoma Surgery'),
                ('SLT', 'Selective laser trabeculoplasty', 'Glaucoma Laser'),
                ('ALT', 'Argon laser trabeculoplasty', 'Glaucoma Laser'),
                ('LPI', 'Laser peripheral iridotomy', 'Glaucoma Laser'),
                ('PPV', 'Pars plana vitrectomy', 'Vitreoretinal Surgery'),
                ('PPV-MB', 'PPV with membrane peeling', 'Vitreoretinal Surgery'),
                ('PPV-RD', 'PPV for retinal detachment', 'Vitreoretinal Surgery'),
                ('PPV-MH', 'PPV for macular hole', 'Vitreoretinal Surgery'),
                ('SB', 'Scleral buckle', 'Vitreoretinal Surgery'),
                ('PNEUMO', 'Pneumatic retinopexy', 'Vitreoretinal Surgery'),
                ('SILICONE', 'Silicone oil injection', 'Vitreoretinal Surgery'),
                ('OIL-REM', 'Silicone oil removal', 'Vitreoretinal Surgery'),
                ('PRP', 'Panretinal photocoagulation', 'Retinal Laser'),
                ('FOCAL', 'Focal laser photocoagulation', 'Retinal Laser'),
                ('GRID', 'Grid laser photocoagulation', 'Retinal Laser'),
                ('BARR', 'Barrier laser photocoagulation', 'Retinal Laser'),
                ('PDT', 'Photodynamic therapy', 'Retinal Laser'),
                ('IVTI', 'Intravitreal anti-VEGF injection', 'Intravitreal Injection'),
                ('IVTI-STER', 'Intravitreal steroid injection', 'Intravitreal Injection'),
                ('IMPL-DEX', 'Dexamethasone implant (Ozurdex)', 'Intravitreal Injection'),
                ('IMPL-FA', 'Fluocinolone acetonide implant (Iluvien)', 'Intravitreal Injection'),
                ('PKP', 'Penetrating keratoplasty', 'Corneal Surgery'),
                ('DALK', 'Deep anterior lamellar keratoplasty', 'Corneal Surgery'),
                ('DSAEK', 'Descemet stripping automated endothelial keratoplasty', 'Corneal Surgery'),
                ('DMEK', 'Descemet membrane endothelial keratoplasty', 'Corneal Surgery'),
                ('PTK', 'Phototherapeutic keratectomy', 'Corneal Surgery'),
                ('LASIK', 'Laser-assisted in situ keratomileusis', 'Refractive Surgery'),
                ('PRK', 'Photorefractive keratectomy', 'Refractive Surgery'),
                ('SMILE', 'Small incision lenticule extraction', 'Refractive Surgery'),
                ('YAG-CAPS', 'YAG laser posterior capsulotomy', 'Other Laser'),
                ('YAG-LPI', 'YAG laser peripheral iridotomy', 'Other Laser'),
                ('EVISCERATION', 'Evisceration', 'Other Surgery'),
                ('ENUCLEATION', 'Enucleation', 'Other Surgery'),
            ]

            cur.executemany('''
                INSERT INTO surgeries (code, description, category, active)
                VALUES (%s, %s, %s, TRUE)
            ''', surgeries)
            conn.commit()
            print(f"Inserted {len(surgeries)} surgery codes")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
        conn.close()
        return False


# Authentication and Utility Functions

def login_required(f):
    """Decorator to require login for routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator to require administrator role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'Administrator':
            flash('Administrator access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


def staff_or_admin_required(f):
    """Decorator to require staff or administrator role"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        if session.get('role') not in ['Administrator', 'Staff']:
            flash('Staff or Administrator access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


def generate_person_hash(mbo):
    """Generate SHA-256 hash from MBO"""
    return hashlib.sha256(mbo.encode()).hexdigest()


def calculate_age(date_of_birth, date_of_sample):
    """Calculate age at sample collection"""
    if not date_of_birth or not date_of_sample:
        return None
    age = date_of_sample.year - date_of_birth.year
    if (date_of_sample.month, date_of_sample.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def get_next_available_patient_id():
    """Get next available patient ID based on highest existing ID in database"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        # Get the highest patient_id currently in use
        cur.execute("SELECT COALESCE(MAX(patient_id), %s) FROM patients_sensitive", (STARTING_PATIENT_ID - 1,))
        max_id = cur.fetchone()[0]
        next_id = max_id + 1

        # Make sure we don't exceed the maximum allowed ID
        if next_id > 99999:
            cur.close()
            conn.close()
            return None

        cur.close()
        conn.close()
        return next_id
    except Exception as e:
        print(f"Error getting next patient ID: {e}")
        if conn:
            conn.close()
        return None


def check_patient_id_exists(patient_id):
    """Check if patient ID already exists"""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM patients_sensitive WHERE patient_id = %s", (patient_id,))
        exists = cur.fetchone()[0] > 0
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        print(f"Error checking patient ID: {e}")
        if conn:
            conn.close()
        return False


def build_filter_clause(request_form):
    """
    Build WHERE clause and parameters for filtering patients based on form data

    Returns:
        tuple: (where_clause, params_list)
            where_clause: SQL WHERE conditions as string
            params_list: List of parameter values for parameterized query
    """
    where_clauses = []
    params = []

    # ============================================================================
    # MAIN OCULAR CONDITIONS FILTERS
    # ============================================================================

    # Glaucoma filter
    glaucoma_filter = request_form.get('filter_glaucoma', '')
    if glaucoma_filter:
        if glaucoma_filter == 'all':
            # Include all patients (no filter needed, just documenting)
            pass
        elif glaucoma_filter == '0':
            where_clauses.append('oc.glaucoma = %s')
            params.append('0')  # FIXED: String instead of integer
        elif glaucoma_filter == '1':
            where_clauses.append('oc.glaucoma = %s')
            params.append('1')  # FIXED: String instead of integer
        elif glaucoma_filter == 'ND':
            where_clauses.append("(oc.glaucoma IS NULL OR oc.glaucoma = 'ND')")
        elif glaucoma_filter == 'not_0_not_nd':
            where_clauses.append("(oc.glaucoma IS NOT NULL AND oc.glaucoma != 'ND' AND oc.glaucoma != '0')")

    # Diabetic Retinopathy filter
    dr_filter = request_form.get('filter_diabetic_retinopathy', '')
    if dr_filter:
        if dr_filter == 'all':
            pass
        elif dr_filter == '0':
            where_clauses.append('oc.diabetic_retinopathy = %s')
            params.append('0')  # FIXED: String instead of integer
        elif dr_filter == '1':
            where_clauses.append('oc.diabetic_retinopathy = %s')
            params.append('1')  # FIXED: String instead of integer
        elif dr_filter == 'ND':
            where_clauses.append("(oc.diabetic_retinopathy IS NULL OR oc.diabetic_retinopathy = 'ND')")
        elif dr_filter == 'not_0_not_nd':
            where_clauses.append(
                "(oc.diabetic_retinopathy IS NOT NULL AND oc.diabetic_retinopathy != 'ND' AND oc.diabetic_retinopathy != '0')")

    # Lens Status filter
    lens_filter = request_form.get('filter_lens_status', '')
    if lens_filter:
        if lens_filter == 'all':
            pass
        elif lens_filter == 'ND':
            where_clauses.append("(oc.lens_status IS NULL OR oc.lens_status = 'ND')")
        elif lens_filter in ['Phakic', 'Pseudophakic', 'Aphakic']:
            where_clauses.append('oc.lens_status = %s')
            params.append(lens_filter)

    # Macular Edema filter
    me_filter = request_form.get('filter_macular_edema', '')
    if me_filter:
        if me_filter == 'all':
            pass
        elif me_filter == '0':
            where_clauses.append('oc.macular_edema = %s')
            params.append('0')  # FIXED: String instead of integer
        elif me_filter == '1':
            where_clauses.append('oc.macular_edema = %s')
            params.append('1')  # FIXED: String instead of integer
        elif me_filter == 'ND':
            where_clauses.append("(oc.macular_edema IS NULL OR oc.macular_edema = 'ND')")
        elif me_filter == 'not_0_not_nd':
            where_clauses.append(
                "(oc.macular_edema IS NOT NULL AND oc.macular_edema != 'ND' AND oc.macular_edema != '0')")

    # Macular Degeneration filter
    md_filter = request_form.get('filter_macular_degeneration', '')
    if md_filter:
        if md_filter == 'all':
            pass
        elif md_filter == '0':
            where_clauses.append('oc.macular_degeneration_dystrophy = %s')
            params.append('0')  # FIXED: String instead of integer
        elif md_filter == '1':
            where_clauses.append('oc.macular_degeneration_dystrophy = %s')
            params.append('1')  # FIXED: String instead of integer
        elif md_filter == 'ND':
            where_clauses.append(
                "(oc.macular_degeneration_dystrophy IS NULL OR oc.macular_degeneration_dystrophy = 'ND')")
        elif md_filter == 'not_0_not_nd':
            where_clauses.append(
                "(oc.macular_degeneration_dystrophy IS NOT NULL AND oc.macular_degeneration_dystrophy != 'ND' AND oc.macular_degeneration_dystrophy != '0')")

    # Epiretinal Membrane filter
    erm_filter = request_form.get('filter_epiretinal_membrane', '')
    if erm_filter:
        if erm_filter == 'all':
            pass
        elif erm_filter == '0':
            where_clauses.append('oc.epiretinal_membrane = %s')
            params.append('0')  # FIXED: String instead of integer
        elif erm_filter == '1':
            where_clauses.append('oc.epiretinal_membrane = %s')
            params.append('1')  # FIXED: String instead of integer
        elif erm_filter == 'ND':
            where_clauses.append("(oc.epiretinal_membrane IS NULL OR oc.epiretinal_membrane = 'ND')")
        elif erm_filter == 'not_0_not_nd':
            where_clauses.append(
                "(oc.epiretinal_membrane IS NOT NULL AND oc.epiretinal_membrane != 'ND' AND oc.epiretinal_membrane != '0')")

    # ============================================================================
    # REPEATABLE CATEGORY FILTERS (Other Conditions, Surgeries, Medications)
    # ============================================================================

    # Other Ocular Conditions filter
    other_ocular_filter = request_form.get('filter_other_ocular_mode', '')
    if other_ocular_filter:
        if other_ocular_filter == 'all':
            # Patient has at least one other ocular condition
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM other_ocular_conditions ooc 
                    WHERE ooc.patient_id = ps.patient_id
                )
            ''')
        elif other_ocular_filter == '0':
            # Patient has no other ocular conditions
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM other_ocular_conditions ooc 
                    WHERE ooc.patient_id = ps.patient_id
                )
            ''')
        elif other_ocular_filter == 'ND':
            # Typically ND for repeatable categories means no data
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM other_ocular_conditions ooc 
                    WHERE ooc.patient_id = ps.patient_id
                )
            ''')
        elif other_ocular_filter == 'not_0_not_nd':
            # Patient has at least one condition
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM other_ocular_conditions ooc 
                    WHERE ooc.patient_id = ps.patient_id
                )
            ''')

    # Surgeries filter
    surgeries_filter = request_form.get('filter_surgeries_mode', '')
    if surgeries_filter:
        if surgeries_filter == 'all':
            # Patient has at least one surgery
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM previous_ocular_surgeries pos 
                    WHERE pos.patient_id = ps.patient_id
                )
            ''')
        elif surgeries_filter == '0':
            # Patient has no surgeries
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM previous_ocular_surgeries pos 
                    WHERE pos.patient_id = ps.patient_id
                )
            ''')
        elif surgeries_filter == 'ND':
            # No surgeries
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM previous_ocular_surgeries pos 
                    WHERE pos.patient_id = ps.patient_id
                )
            ''')
        elif surgeries_filter == 'not_0_not_nd':
            # Patient has at least one surgery
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM previous_ocular_surgeries pos 
                    WHERE pos.patient_id = ps.patient_id
                )
            ''')

    # Ocular Medications filter
    ocular_meds_filter = request_form.get('filter_ocular_meds_mode', '')
    if ocular_meds_filter:
        if ocular_meds_filter == 'all':
            # Patient has at least one ocular medication
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM ocular_medications om 
                    WHERE om.patient_id = ps.patient_id
                )
            ''')
        elif ocular_meds_filter == '0':
            # Patient has no ocular medications
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM ocular_medications om 
                    WHERE om.patient_id = ps.patient_id
                )
            ''')
        elif ocular_meds_filter == 'ND':
            # No ocular medications
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM ocular_medications om 
                    WHERE om.patient_id = ps.patient_id
                )
            ''')
        elif ocular_meds_filter == 'not_0_not_nd':
            # Patient has at least one ocular medication
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM ocular_medications om 
                    WHERE om.patient_id = ps.patient_id
                )
            ''')

    # Systemic Medications filter
    systemic_meds_filter = request_form.get('filter_systemic_meds_mode', '')
    if systemic_meds_filter:
        if systemic_meds_filter == 'all':
            # Patient has at least one systemic medication
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM systemic_medications sm 
                    WHERE sm.patient_id = ps.patient_id
                )
            ''')
        elif systemic_meds_filter == '0':
            # Patient has no systemic medications
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM systemic_medications sm 
                    WHERE sm.patient_id = ps.patient_id
                )
            ''')
        elif systemic_meds_filter == 'ND':
            # No systemic medications
            where_clauses.append('''
                NOT EXISTS (
                    SELECT 1 FROM systemic_medications sm 
                    WHERE sm.patient_id = ps.patient_id
                )
            ''')
        elif systemic_meds_filter == 'not_0_not_nd':
            # Patient has at least one systemic medication
            where_clauses.append('''
                EXISTS (
                    SELECT 1 FROM systemic_medications sm 
                    WHERE sm.patient_id = ps.patient_id
                )
            ''')

    # Build final WHERE clause
    if where_clauses:
        where_clause = ' AND ' + ' AND '.join(where_clauses)
    else:
        where_clause = ''

    return where_clause, params


# Routes

@app.route('/')
def index():
    """Redirect to dashboard if logged in, otherwise to login"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('login.html')

        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cur.fetchone()

            if user and bcrypt.check_password_hash(user['password_hash'], password):
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']

                # Update last login
                cur.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s', (user['user_id'],))
                conn.commit()

                cur.close()
                conn.close()

                flash(f'Welcome back, {username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')
                cur.close()
                conn.close()
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
            if conn:
                conn.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('dashboard.html', stats={})

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get statistics
        cur.execute('SELECT COUNT(*) as total FROM patients_sensitive')
        total_patients = cur.fetchone()['total']

        cur.execute('SELECT COUNT(*) as total FROM users')
        total_users = cur.fetchone()['total']

        # Get next available patient ID (based on actual database content)
        next_patient_id = get_next_available_patient_id()

        stats = {
            'total_patients': total_patients,
            'total_users': total_users,
            'next_patient_id': next_patient_id
        }

        cur.close()
        conn.close()

        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        if conn:
            conn.close()
        return render_template('dashboard.html', stats={})


@app.route('/api/check-patient-id/<int:patient_id>')
@staff_or_admin_required
def api_check_patient_id(patient_id):
    """API endpoint to check if patient ID exists"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed', 'exists': True}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM patients_sensitive WHERE patient_id = %s", (patient_id,))
        count = cur.fetchone()[0]
        exists = count > 0

        cur.close()
        conn.close()

        return jsonify({
            'exists': exists,
            'patient_id': patient_id,
            'available': not exists
        })
    except Exception as e:
        print(f"[API] Error checking patient ID {patient_id}: {e}")
        if conn:
            conn.close()
        return jsonify({'error': str(e), 'exists': True}), 500


@app.route('/api/next-patient-id')
@staff_or_admin_required
def api_next_patient_id():
    """API endpoint to get next available patient ID"""
    next_id = get_next_available_patient_id()
    if next_id:
        return jsonify({'patient_id': next_id, 'available': True})
    return jsonify({'error': 'Could not generate patient ID'}), 500


# New Patient Route

@app.route('/new-patient', methods=['GET', 'POST'])
@staff_or_admin_required
def new_patient():
    """Create new patient record"""
    if request.method == 'GET':
        # Get reference data for dropdowns
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('dashboard'))

        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get ICD-10 ocular conditions
            cur.execute('SELECT code, description FROM icd10_ocular_conditions WHERE active = TRUE ORDER BY code')
            icd10_ocular = cur.fetchall()

            # Get ICD-10 systemic conditions
            cur.execute('SELECT code, description FROM icd10_systemic_conditions WHERE active = TRUE ORDER BY code')
            icd10_systemic = cur.fetchall()

            # Get medications
            cur.execute(
                'SELECT trade_name, generic_name, medication_type FROM medications WHERE active = TRUE ORDER BY trade_name')
            medications = cur.fetchall()

            # Get surgeries
            cur.execute('SELECT code, description FROM surgeries WHERE active = TRUE ORDER BY code')
            surgeries = cur.fetchall()

            # Get next patient ID based on actual database content
            next_id = get_next_available_patient_id()

            cur.close()
            conn.close()

            # Prepare stats with default values (in case template needs them)
            stats = {
                'total_patients': 0,
                'total_users': 0,
                'next_patient_id': next_id
            }

            return render_template('new_patient.html',
                                   icd10_ocular=icd10_ocular,
                                   icd10_systemic=icd10_systemic,
                                   medications=medications,
                                   surgeries=surgeries,
                                   next_patient_id=next_id,
                                   stats=stats)
        except Exception as e:
            flash(f'Error loading form: {str(e)}', 'error')
            if conn:
                conn.close()
            return redirect(url_for('dashboard'))

    # POST - save new patient
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('new_patient'))

    try:
        cur = conn.cursor()

        # Get form data - General Data
        patient_id = int(request.form.get('patient_id'))
        patient_name = request.form.get('patient_name')
        mbo = request.form.get('mbo')
        sex = request.form.get('sex')

        # Parse dates from separate day/month/year fields
        dob_day = request.form.get('dob_day')
        dob_month = request.form.get('dob_month')
        dob_year = request.form.get('dob_year')
        if dob_day and dob_month and dob_year:
            date_of_birth = date(int(dob_year), int(dob_month), int(dob_day))
        else:
            date_of_birth = None

        collection_day = request.form.get('collection_day')
        collection_month = request.form.get('collection_month')
        collection_year = request.form.get('collection_year')
        if collection_day and collection_month and collection_year:
            date_of_sample_collection = date(int(collection_year), int(collection_month), int(collection_day))
        else:
            date_of_sample_collection = None

        eye = request.form.get('eye')

        # Check if patient ID already exists
        if check_patient_id_exists(patient_id):
            flash(f'Patient ID {patient_id} already exists. Please use a different ID.', 'error')
            conn.close()
            return redirect(url_for('new_patient'))

        # Generate person hash and calculate age
        person_hash = generate_person_hash(mbo)
        age = calculate_age(date_of_birth, date_of_sample_collection)

        # Insert into patients_sensitive
        cur.execute('''
            INSERT INTO patients_sensitive (patient_id, patient_name, mbo, date_of_birth, date_of_sample_collection)
            VALUES (%s, %s, %s, %s, %s)
        ''', (patient_id, patient_name, mbo, date_of_birth, date_of_sample_collection))

        # Insert into patients_statistical
        cur.execute('''
            INSERT INTO patients_statistical (patient_id, person_hash, age, sex, eye)
            VALUES (%s, %s, %s, %s, %s)
        ''', (patient_id, person_hash, age, sex, eye))

        # Main Ocular Conditions
        lens_status = request.form.get('lens_status', 'ND')
        locs_iii_no = request.form.get('locs_no', 'ND')
        locs_iii_nc = request.form.get('locs_nc', 'ND')
        locs_iii_c = request.form.get('locs_c', 'ND')
        locs_iii_p = request.form.get('locs_p', 'ND')
        iol_type = request.form.get('iol_type', 'ND')
        etiology_aphakia = request.form.get('aphakia_etiology', 'ND')

        glaucoma = request.form.get('glaucoma', 'ND')
        oht_or_pac = request.form.get('oht_or_pac', 'ND')
        etiology_glaucoma = request.form.get('glaucoma_etiology', 'ND')
        steroid_responder = request.form.get('steroid_responder', 'ND')
        pxs = request.form.get('pxs', '0')
        pds = request.form.get('pds', '0')

        diabetic_retinopathy = request.form.get('diabetic_retinopathy', '0')
        stage_diabetic_retinopathy = request.form.get('dr_stage', 'ND')
        stage_npdr = request.form.get('npdr_stage', 'ND')
        stage_pdr = request.form.get('pdr_stage', 'ND')

        macular_edema = request.form.get('macular_edema', '0')
        etiology_macular_edema = request.form.get('me_etiology', 'ND')

        macular_degeneration_dystrophy = request.form.get('macular_degeneration', '0')
        etiology_macular_deg_dyst = request.form.get('md_etiology', 'ND')
        stage_amd = request.form.get('amd_stage', 'ND')
        exudation_amd = request.form.get('amd_exudation', 'ND')
        stage_other_macular_deg = request.form.get('other_md_stage', 'ND')
        exudation_other_macular_deg = request.form.get('other_md_exudation', 'ND')

        macular_hole_vmt = request.form.get('mh_vmt', '0')
        etiology_mh_vmt = request.form.get('mh_vmt_etiology', 'ND')
        cause_secondary_mh_vmt = request.form.get('secondary_mh_vmt_cause', 'ND')
        treatment_status_mh_vmt = request.form.get('mh_vmt_treatment_status', 'ND')

        epiretinal_membrane = request.form.get('epiretinal_membrane', '0')
        etiology_erm = request.form.get('erm_etiology', 'ND')
        cause_secondary_erm = request.form.get('secondary_erm_cause', 'ND')
        treatment_status_erm = request.form.get('erm_treatment_status', 'ND')

        retinal_detachment = request.form.get('retinal_detachment', '0')
        etiology_rd = request.form.get('rd_etiology', 'ND')
        treatment_status_rd = request.form.get('rd_treatment_status', 'ND')
        pvr = request.form.get('pvr', 'ND')

        vitreous_haemorrhage_opacification = request.form.get('vitreous_opacification', '0')
        etiology_vitreous_haemorrhage = request.form.get('vh_etiology', 'ND')

        # Insert ocular conditions
        cur.execute('''
            INSERT INTO ocular_conditions (
                patient_id, lens_status, locs_iii_no, locs_iii_nc, locs_iii_c, locs_iii_p,
                iol_type, etiology_aphakia, glaucoma, oht_or_pac, etiology_glaucoma,
                steroid_responder, pxs, pds, diabetic_retinopathy, stage_diabetic_retinopathy,
                stage_npdr, stage_pdr, macular_edema, etiology_macular_edema,
                macular_degeneration_dystrophy, etiology_macular_deg_dyst, stage_amd, exudation_amd,
                stage_other_macular_deg, exudation_other_macular_deg, macular_hole_vmt, etiology_mh_vmt,
                cause_secondary_mh_vmt, treatment_status_mh_vmt, epiretinal_membrane, etiology_erm,
                cause_secondary_erm, treatment_status_erm, retinal_detachment, etiology_rd,
                treatment_status_rd, pvr, vitreous_haemorrhage_opacification, etiology_vitreous_haemorrhage
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (patient_id, lens_status, locs_iii_no, locs_iii_nc, locs_iii_c, locs_iii_p,
              iol_type, etiology_aphakia, glaucoma, oht_or_pac, etiology_glaucoma,
              steroid_responder, pxs, pds, diabetic_retinopathy, stage_diabetic_retinopathy,
              stage_npdr, stage_pdr, macular_edema, etiology_macular_edema,
              macular_degeneration_dystrophy, etiology_macular_deg_dyst, stage_amd, exudation_amd,
              stage_other_macular_deg, exudation_other_macular_deg, macular_hole_vmt, etiology_mh_vmt,
              cause_secondary_mh_vmt, treatment_status_mh_vmt, epiretinal_membrane, etiology_erm,
              cause_secondary_erm, treatment_status_erm, retinal_detachment, etiology_rd,
              treatment_status_rd, pvr, vitreous_haemorrhage_opacification, etiology_vitreous_haemorrhage))

        # Other Ocular Conditions (multiple entries possible)
        other_ocular_conditions = request.form.getlist('other_ocular_condition[]')
        other_ocular_eyes = request.form.getlist('other_ocular_condition_eye[]')
        for icd10_code, eye_affected in zip(other_ocular_conditions, other_ocular_eyes):
            if icd10_code and icd10_code not in ['0', 'ND']:
                cur.execute('''
                    INSERT INTO other_ocular_conditions (patient_id, icd10_code, eye)
                    VALUES (%s, %s, %s)
                ''', (patient_id, icd10_code, eye_affected))

        # Previous Ocular Surgeries (multiple entries possible)
        surgeries_list = request.form.getlist('previous_surgery[]')
        surgeries_eyes = request.form.getlist('previous_surgery_eye[]')
        for surgery_code, eye_affected in zip(surgeries_list, surgeries_eyes):
            if surgery_code and surgery_code not in ['0', 'ND']:
                cur.execute('''
                    INSERT INTO previous_ocular_surgeries (patient_id, surgery_code, eye)
                    VALUES (%s, %s, %s)
                ''', (patient_id, surgery_code, eye_affected))

        # Systemic Conditions (multiple entries possible)
        systemic_conditions_list = request.form.getlist('systemic_condition[]')
        for icd10_code in systemic_conditions_list:
            if icd10_code and icd10_code not in ['0', 'ND']:
                cur.execute('''
                    INSERT INTO systemic_conditions (patient_id, icd10_code)
                    VALUES (%s, %s)
                ''', (patient_id, icd10_code))

        # Ocular Medications (multiple entries possible)
        ocular_meds_list = request.form.getlist('ocular_medication[]')
        ocular_meds_eyes = request.form.getlist('ocular_medication_eye[]')
        ocular_meds_days = request.form.getlist('ocular_medication_days[]')

        for medication, eye_affected, last_app in zip(ocular_meds_list, ocular_meds_eyes, ocular_meds_days):
            if medication and medication not in ['0', 'ND']:
                # Split medication into trade_name|generic_name
                parts = medication.split('|')
                if len(parts) == 2:
                    trade_name, generic_name = parts
                    last_application_days = int(last_app) if last_app and last_app.isdigit() else None
                    cur.execute('''
                        INSERT INTO ocular_medications (patient_id, trade_name, generic_name, eye, last_application_days)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (patient_id, trade_name, generic_name, eye_affected, last_application_days))

        # Systemic Medications (multiple entries possible)
        systemic_meds_list = request.form.getlist('systemic_medication[]')
        systemic_meds_days = request.form.getlist('systemic_medication_days[]')

        for medication, last_app in zip(systemic_meds_list, systemic_meds_days):
            if medication and medication not in ['0', 'ND']:
                # Split medication into trade_name|generic_name
                parts = medication.split('|')
                if len(parts) == 2:
                    trade_name, generic_name = parts
                    last_application_days = int(last_app) if last_app and last_app.isdigit() else None
                    cur.execute('''
                        INSERT INTO systemic_medications (patient_id, trade_name, generic_name, last_application_days)
                        VALUES (%s, %s, %s, %s)
                    ''', (patient_id, trade_name, generic_name, last_application_days))

        conn.commit()
        cur.close()
        conn.close()

        flash(f'Patient #{patient_id:05d} - {patient_name} has been added successfully!', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        conn.rollback()
        flash(f'Error saving patient: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('new_patient'))


# Validate Data / Edit Patient Routes

@app.route('/validate-data', methods=['GET', 'POST'])
@staff_or_admin_required
def validate_data():
    """Search and list patients for validation with optional filtering"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('validate_data.html', patients=[])

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get search parameters (from GET for search, POST for filters)
        search_type = request.args.get('type', 'id')
        search_query = request.args.get('q', '')

        # Check if filters are being used (POST request with filters)
        using_filters = request.method == 'POST' and request.form.get('use_filters') == '1'

        # Base query
        base_query = '''
            SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, ps.date_of_sample_collection,
                   pst.sex, pst.eye
            FROM patients_sensitive ps
            JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
        '''

        params = []
        where_clauses = []

        if using_filters:
            # Use the existing build_filter_clause function for filtering
            # Need to join with ocular_conditions table for filter support
            base_query = '''
                SELECT DISTINCT ps.patient_id, ps.patient_name, ps.date_of_birth, 
                       ps.date_of_sample_collection, pst.sex, pst.eye
                FROM patients_sensitive ps
                JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                LEFT JOIN ocular_conditions oc ON ps.patient_id = oc.patient_id
                WHERE 1=1
            '''

            # Build filter clause using existing function
            filter_clause, filter_params = build_filter_clause(request.form)
            base_query += filter_clause
            params.extend(filter_params)

            # Add search query on top of filters if provided
            if search_query:
                if search_type == 'id':
                    base_query += ' AND CAST(ps.patient_id AS TEXT) LIKE %s'
                    params.append(f'%{search_query}%')
                elif search_type == 'name':
                    base_query += ' AND LOWER(ps.patient_name) LIKE LOWER(%s)'
                    params.append(f'%{search_query}%')
                elif search_type == 'mbo':
                    base_query += ' AND ps.mbo LIKE %s'
                    params.append(f'%{search_query}%')

            base_query += ' ORDER BY ps.patient_id DESC LIMIT 100'

        elif search_query:
            # Traditional search without filters
            if search_type == 'id':
                base_query += '''
                    WHERE CAST(ps.patient_id AS TEXT) LIKE %s
                    ORDER BY ps.patient_id DESC
                    LIMIT 20
                '''
                params.append(f'%{search_query}%')
            elif search_type == 'name':
                base_query += '''
                    WHERE LOWER(ps.patient_name) LIKE LOWER(%s)
                    ORDER BY ps.patient_id DESC
                    LIMIT 20
                '''
                params.append(f'%{search_query}%')
            elif search_type == 'mbo':
                base_query += '''
                    WHERE ps.mbo LIKE %s
                    ORDER BY ps.patient_id DESC
                    LIMIT 20
                '''
                params.append(f'%{search_query}%')
        else:
            # Show 20 most recent patients if no search query or filters
            base_query += 'ORDER BY ps.patient_id DESC LIMIT 20'

        # Execute query
        if params:
            cur.execute(base_query, params)
        else:
            cur.execute(base_query)

        patients = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('validate_data.html',
                               patients=patients,
                               search_type=search_type,
                               search_query=search_query,
                               using_filters=using_filters,
                               filters=request.form if using_filters else {})

    except Exception as e:
        flash(f'Error searching patients: {str(e)}', 'error')
        if conn:
            conn.close()
        return render_template('validate_data.html',
                               patients=[],
                               search_type=search_type,
                               search_query=search_query)


@app.route('/edit-patient/<int:patient_id>', methods=['GET', 'POST'])
@staff_or_admin_required
def edit_patient(patient_id):
    """Edit existing patient record"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('validate_data'))

    if request.method == 'GET':
        # Load patient data and reference lists
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get patient data
            cur.execute('''
                SELECT ps.*, pst.sex, pst.eye, pst.age
                FROM patients_sensitive ps
                JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                WHERE ps.patient_id = %s
            ''', (patient_id,))
            patient = cur.fetchone()

            if not patient:
                flash(f'Patient #{patient_id} not found', 'error')
                cur.close()
                conn.close()
                return redirect(url_for('validate_data'))

            # Get ocular conditions
            cur.execute('SELECT * FROM ocular_conditions WHERE patient_id = %s', (patient_id,))
            ocular_conditions = cur.fetchone()

            # Get other ocular conditions
            cur.execute('SELECT * FROM other_ocular_conditions WHERE patient_id = %s', (patient_id,))
            other_ocular = cur.fetchall()

            # Get previous surgeries
            cur.execute('SELECT * FROM previous_ocular_surgeries WHERE patient_id = %s', (patient_id,))
            surgeries = cur.fetchall()

            # Get systemic conditions
            cur.execute('SELECT * FROM systemic_conditions WHERE patient_id = %s', (patient_id,))
            systemic = cur.fetchall()

            # Get ocular medications
            cur.execute('SELECT * FROM ocular_medications WHERE patient_id = %s', (patient_id,))
            ocular_meds = cur.fetchall()

            # Get systemic medications
            cur.execute('SELECT * FROM systemic_medications WHERE patient_id = %s', (patient_id,))
            systemic_meds = cur.fetchall()

            # Get reference data for dropdowns
            cur.execute('SELECT code, description FROM icd10_ocular_conditions WHERE active = TRUE ORDER BY code')
            icd10_ocular = cur.fetchall()

            cur.execute('SELECT code, description FROM icd10_systemic_conditions WHERE active = TRUE ORDER BY code')
            icd10_systemic = cur.fetchall()

            cur.execute(
                'SELECT trade_name, generic_name, medication_type FROM medications WHERE active = TRUE ORDER BY trade_name')
            medications = cur.fetchall()

            cur.execute('SELECT code, description FROM surgeries WHERE active = TRUE ORDER BY code')
            surgeries_list = cur.fetchall()

            cur.close()
            conn.close()

            # Prepare stats with default values (in case template needs them)
            stats = {
                'total_patients': 0,
                'total_users': 0,
                'next_patient_id': STARTING_PATIENT_ID
            }

            return render_template('edit_patient.html',
                                   patient=patient,
                                   ocular_conditions=ocular_conditions,
                                   other_conditions=other_ocular,
                                   surgeries=surgeries,
                                   systemic=systemic,
                                   ocular_meds=ocular_meds,
                                   systemic_meds=systemic_meds,
                                   icd10_ocular=icd10_ocular,
                                   icd10_systemic=icd10_systemic,
                                   medications=medications,
                                   surgeries_list=surgeries_list,
                                   stats=stats)
        except Exception as e:
            flash(f'Error loading patient data: {str(e)}', 'error')
            if conn:
                conn.close()
            return redirect(url_for('validate_data'))

    # POST - Update patient data
    try:
        cur = conn.cursor()

        # Get basic patient data
        patient_name = request.form.get('patient_name')
        mbo = request.form.get('mbo')
        sex = request.form.get('sex')
        eye = request.form.get('eye')

        # Get date fields
        dob_day = request.form.get('dob_day')
        dob_month = request.form.get('dob_month')
        dob_year = request.form.get('dob_year')
        dosc_day = request.form.get('collection_day')
        dosc_month = request.form.get('collection_month')
        dosc_year = request.form.get('collection_year')

        # Parse dates
        date_of_birth = None
        if dob_day and dob_month and dob_year:
            try:
                date_of_birth = date(int(dob_year), int(dob_month), int(dob_day))
            except ValueError:
                flash('Invalid date of birth', 'error')
                return redirect(url_for('edit_patient', patient_id=patient_id))

        date_of_sample_collection = None
        if dosc_day and dosc_month and dosc_year:
            try:
                date_of_sample_collection = date(int(dosc_year), int(dosc_month), int(dosc_day))
            except ValueError:
                flash('Invalid sample collection date', 'error')
                return redirect(url_for('edit_patient', patient_id=patient_id))

        # Calculate age and person hash
        age = None
        if date_of_birth and date_of_sample_collection:
            age = date_of_sample_collection.year - date_of_birth.year
            if date_of_sample_collection.month < date_of_birth.month or \
                    (date_of_sample_collection.month == date_of_birth.month and
                     date_of_sample_collection.day < date_of_birth.day):
                age -= 1

        person_hash = hashlib.sha256(mbo.encode()).hexdigest() if mbo else None

        # Update patients_sensitive table
        cur.execute('''
            UPDATE patients_sensitive
            SET patient_name = %s, mbo = %s, date_of_birth = %s, 
                date_of_sample_collection = %s, updated_at = CURRENT_TIMESTAMP
            WHERE patient_id = %s
        ''', (patient_name, mbo, date_of_birth, date_of_sample_collection, patient_id))

        # Update patients_statistical table
        cur.execute('''
            UPDATE patients_statistical
            SET person_hash = %s, age = %s, sex = %s, eye = %s
            WHERE patient_id = %s
        ''', (person_hash, age, sex, eye, patient_id))

        # Get all ocular condition fields
        lens_status = request.form.get('lens_status', 'ND')
        locs_iii_no = request.form.get('locs_no', 'ND')
        locs_iii_nc = request.form.get('locs_nc', 'ND')
        locs_iii_c = request.form.get('locs_c', 'ND')
        locs_iii_p = request.form.get('locs_p', 'ND')
        iol_type = request.form.get('iol_type', 'ND')
        etiology_aphakia = request.form.get('aphakia_etiology', 'ND')
        glaucoma = request.form.get('glaucoma', '0')
        oht_or_pac = request.form.get('oht_or_pac', 'ND')
        etiology_glaucoma = request.form.get('glaucoma_etiology', 'ND')
        steroid_responder = request.form.get('steroid_responder', 'ND')
        pxs = request.form.get('pxs', '0')
        pds = request.form.get('pds', '0')
        diabetic_retinopathy = request.form.get('diabetic_retinopathy', '0')
        stage_diabetic_retinopathy = request.form.get('dr_stage', 'ND')
        stage_npdr = request.form.get('npdr_stage', 'ND')
        stage_pdr = request.form.get('pdr_stage', 'ND')
        macular_edema = request.form.get('macular_edema', '0')
        etiology_macular_edema = request.form.get('me_etiology', 'ND')
        macular_degeneration_dystrophy = request.form.get('macular_degeneration', '0')
        etiology_macular_deg_dyst = request.form.get('md_etiology', 'ND')
        stage_amd = request.form.get('amd_stage', 'ND')
        exudation_amd = request.form.get('amd_exudation', 'ND')
        stage_other_macular_deg = request.form.get('other_md_stage', 'ND')
        exudation_other_macular_deg = request.form.get('other_md_exudation', 'ND')
        macular_hole_vmt = request.form.get('mh_vmt', '0')
        etiology_mh_vmt = request.form.get('mh_vmt_etiology', 'ND')
        cause_secondary_mh_vmt = request.form.get('secondary_mh_vmt_cause', 'ND')
        treatment_status_mh_vmt = request.form.get('mh_vmt_treatment_status', 'ND')
        epiretinal_membrane = request.form.get('epiretinal_membrane', '0')
        etiology_erm = request.form.get('erm_etiology', 'ND')
        cause_secondary_erm = request.form.get('secondary_erm_cause', 'ND')
        treatment_status_erm = request.form.get('erm_treatment_status', 'ND')
        retinal_detachment = request.form.get('retinal_detachment', '0')
        etiology_rd = request.form.get('rd_etiology', 'ND')
        treatment_status_rd = request.form.get('rd_treatment_status', 'ND')
        pvr = request.form.get('pvr', 'ND')
        vitreous_haemorrhage_opacification = request.form.get('vitreous_opacification', '0')
        etiology_vitreous_haemorrhage = request.form.get('vh_etiology', 'ND')

        # Update ocular_conditions table
        cur.execute('''
            UPDATE ocular_conditions
            SET lens_status = %s, locs_iii_no = %s, locs_iii_nc = %s, locs_iii_c = %s, locs_iii_p = %s,
                iol_type = %s, etiology_aphakia = %s, glaucoma = %s, oht_or_pac = %s, etiology_glaucoma = %s,
                steroid_responder = %s, pxs = %s, pds = %s, diabetic_retinopathy = %s,
                stage_diabetic_retinopathy = %s, stage_npdr = %s, stage_pdr = %s, macular_edema = %s,
                etiology_macular_edema = %s, macular_degeneration_dystrophy = %s,
                etiology_macular_deg_dyst = %s, stage_amd = %s, exudation_amd = %s,
                stage_other_macular_deg = %s, exudation_other_macular_deg = %s, macular_hole_vmt = %s,
                etiology_mh_vmt = %s, cause_secondary_mh_vmt = %s, treatment_status_mh_vmt = %s,
                epiretinal_membrane = %s, etiology_erm = %s, cause_secondary_erm = %s,
                treatment_status_erm = %s, retinal_detachment = %s, etiology_rd = %s,
                treatment_status_rd = %s, pvr = %s, vitreous_haemorrhage_opacification = %s,
                etiology_vitreous_haemorrhage = %s, updated_at = CURRENT_TIMESTAMP
            WHERE patient_id = %s
        ''', (lens_status, locs_iii_no, locs_iii_nc, locs_iii_c, locs_iii_p,
              iol_type, etiology_aphakia, glaucoma, oht_or_pac, etiology_glaucoma,
              steroid_responder, pxs, pds, diabetic_retinopathy, stage_diabetic_retinopathy,
              stage_npdr, stage_pdr, macular_edema, etiology_macular_edema,
              macular_degeneration_dystrophy, etiology_macular_deg_dyst, stage_amd, exudation_amd,
              stage_other_macular_deg, exudation_other_macular_deg, macular_hole_vmt, etiology_mh_vmt,
              cause_secondary_mh_vmt, treatment_status_mh_vmt, epiretinal_membrane, etiology_erm,
              cause_secondary_erm, treatment_status_erm, retinal_detachment, etiology_rd,
              treatment_status_rd, pvr, vitreous_haemorrhage_opacification, etiology_vitreous_haemorrhage,
              patient_id))

        # Delete existing many-to-many relationships and re-insert
        cur.execute('DELETE FROM other_ocular_conditions WHERE patient_id = %s', (patient_id,))
        cur.execute('DELETE FROM previous_ocular_surgeries WHERE patient_id = %s', (patient_id,))
        cur.execute('DELETE FROM systemic_conditions WHERE patient_id = %s', (patient_id,))
        cur.execute('DELETE FROM ocular_medications WHERE patient_id = %s', (patient_id,))
        cur.execute('DELETE FROM systemic_medications WHERE patient_id = %s', (patient_id,))

        # Other Ocular Conditions (multiple entries possible)
        other_ocular_conditions = request.form.getlist('other_ocular_condition[]')
        other_ocular_eyes = request.form.getlist('other_ocular_condition_eye[]')
        for icd10_code, eye_affected in zip(other_ocular_conditions, other_ocular_eyes):
            if icd10_code and icd10_code not in ['0', 'ND']:
                cur.execute('''
                    INSERT INTO other_ocular_conditions (patient_id, icd10_code, eye)
                    VALUES (%s, %s, %s)
                ''', (patient_id, icd10_code, eye_affected))

        # Previous Ocular Surgeries (multiple entries possible)
        surgeries_list = request.form.getlist('previous_surgery[]')
        surgeries_eyes = request.form.getlist('previous_surgery_eye[]')
        for surgery_code, eye_affected in zip(surgeries_list, surgeries_eyes):
            if surgery_code and surgery_code not in ['0', 'ND']:
                cur.execute('''
                    INSERT INTO previous_ocular_surgeries (patient_id, surgery_code, eye)
                    VALUES (%s, %s, %s)
                ''', (patient_id, surgery_code, eye_affected))

        # Systemic Conditions (multiple entries possible)
        systemic_conditions_list = request.form.getlist('systemic_condition[]')
        for icd10_code in systemic_conditions_list:
            if icd10_code and icd10_code not in ['0', 'ND']:
                cur.execute('''
                    INSERT INTO systemic_conditions (patient_id, icd10_code)
                    VALUES (%s, %s)
                ''', (patient_id, icd10_code))

        # Ocular Medications (multiple entries possible)
        ocular_meds_list = request.form.getlist('ocular_medication[]')
        ocular_meds_eyes = request.form.getlist('ocular_medication_eye[]')
        ocular_meds_days = request.form.getlist('ocular_medication_days[]')

        for medication, eye_affected, last_app in zip(ocular_meds_list, ocular_meds_eyes, ocular_meds_days):
            if medication and medication not in ['0', 'ND']:
                # Split medication into trade_name|generic_name
                parts = medication.split('|')
                if len(parts) == 2:
                    trade_name, generic_name = parts
                    last_application_days = int(last_app) if last_app and last_app.isdigit() else None
                    cur.execute('''
                        INSERT INTO ocular_medications (patient_id, trade_name, generic_name, eye, last_application_days)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (patient_id, trade_name, generic_name, eye_affected, last_application_days))

        # Systemic Medications (multiple entries possible)
        systemic_meds_list = request.form.getlist('systemic_medication[]')
        systemic_meds_days = request.form.getlist('systemic_medication_days[]')

        for medication, last_app in zip(systemic_meds_list, systemic_meds_days):
            if medication and medication not in ['0', 'ND']:
                # Split medication into trade_name|generic_name
                parts = medication.split('|')
                if len(parts) == 2:
                    trade_name, generic_name = parts
                    last_application_days = int(last_app) if last_app and last_app.isdigit() else None
                    cur.execute('''
                        INSERT INTO systemic_medications (patient_id, trade_name, generic_name, last_application_days)
                        VALUES (%s, %s, %s, %s)
                    ''', (patient_id, trade_name, generic_name, last_application_days))

        conn.commit()
        cur.close()
        conn.close()

        flash(f'Patient #{patient_id:05d} - {patient_name} has been updated successfully!', 'success')
        return redirect(url_for('validate_data'))

    except Exception as e:
        conn.rollback()
        flash(f'Error updating patient: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('edit_patient', patient_id=patient_id))


# Export Data Route

@app.route('/export_data', methods=['GET', 'POST'])
@login_required
def export_data():
    """Export statistical data with BINARY COLUMNS - each medication/condition/surgery gets its own column"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('export_data.html',
                               stats={'total_patients': 0, 'gender': {'M': 0, 'F': 0}, 'age_distribution': []})

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get statistics for display
        cur.execute('SELECT COUNT(*) as total FROM patients_sensitive')
        total_patients = cur.fetchone()['total']

        cur.execute('''
            SELECT sex, COUNT(*) as count
            FROM patients_statistical
            WHERE sex IN ('M', 'F')
            GROUP BY sex
        ''')
        gender_stats = cur.fetchall()
        gender = {'M': 0, 'F': 0}
        for row in gender_stats:
            gender[row['sex']] = row['count']

        # Age distribution
        cur.execute('''
            SELECT 
                CASE 
                    WHEN age < 18 THEN '0-17'
                    WHEN age < 30 THEN '18-29'
                    WHEN age < 40 THEN '30-39'
                    WHEN age < 50 THEN '40-49'
                    WHEN age < 60 THEN '50-59'
                    WHEN age < 70 THEN '60-69'
                    WHEN age < 80 THEN '70-79'
                    ELSE '80+'
                END as age_group,
                COUNT(*) as count
            FROM patients_statistical
            WHERE age IS NOT NULL
            GROUP BY age_group
            ORDER BY age_group
        ''')
        age_distribution = [(row['age_group'], row['count']) for row in cur.fetchall()]

        stats = {
            'total_patients': total_patients,
            'gender': gender,
            'age_distribution': age_distribution
        }

        if request.method == 'POST':
            # Handle export
            export_format = request.form.get('format', 'csv')
            data_type = request.form.get('data_type', 'anonymized')

            # Staff can only export anonymized data
            if session.get('role') == 'Staff':
                data_type = 'anonymized'

            # Get date range if provided
            date_from = request.form.get('date_from')
            date_to = request.form.get('date_to')

            # Get data inclusion options
            include_conditions = 'include_conditions' in request.form
            include_other_conditions = 'include_other_conditions' in request.form
            include_surgeries = 'include_surgeries' in request.form
            include_systemic = 'include_systemic' in request.form
            include_medications = 'include_medications' in request.form

            # ============================================================
            # STEP 1: Query all reference data (including inactive items used by any patient)
            # ============================================================

            # Get all medications (active OR used by patients)
            cur.execute('''
                SELECT DISTINCT generic_name
                FROM (
                    SELECT generic_name FROM medications WHERE active = TRUE
                    UNION
                    SELECT DISTINCT generic_name FROM ocular_medications
                    UNION
                    SELECT DISTINCT generic_name FROM systemic_medications
                ) AS all_meds
                ORDER BY generic_name
            ''')
            all_medications = [row['generic_name'] for row in cur.fetchall()]

            # Get all ocular ICD-10 codes (active OR used by patients)
            cur.execute('''
                SELECT DISTINCT code
                FROM (
                    SELECT code FROM icd10_ocular_conditions WHERE active = TRUE
                    UNION
                    SELECT DISTINCT icd10_code AS code FROM other_ocular_conditions
                ) AS all_codes
                ORDER BY code
            ''')
            all_ocular_codes = [row['code'] for row in cur.fetchall()]

            # Get all systemic ICD-10 codes (active OR used by patients)
            cur.execute('''
                SELECT DISTINCT code
                FROM (
                    SELECT code FROM icd10_systemic_conditions WHERE active = TRUE
                    UNION
                    SELECT DISTINCT icd10_code AS code FROM systemic_conditions
                ) AS all_codes
                ORDER BY code
            ''')
            all_systemic_codes = [row['code'] for row in cur.fetchall()]

            # Get all surgery codes (active OR used by patients)
            # FIXED: surgeries table uses 'code' not 'surgery_code'
            cur.execute('''
                SELECT DISTINCT code
                FROM (
                    SELECT code FROM surgeries WHERE active = TRUE
                    UNION
                    SELECT DISTINCT surgery_code AS code FROM previous_ocular_surgeries
                ) AS all_surgeries
                ORDER BY code
            ''')
            all_surgeries = [row['code'] for row in cur.fetchall()]

            # ============================================================
            # STEP 2: Build base query for patients
            # ============================================================

            if data_type == 'sensitive' and session.get('role') == 'Administrator':
                # Sensitive export - includes names and MBO
                base_query = '''
                    SELECT 
                        ps.patient_id,
                        ps.patient_name,
                        ps.mbo,
                        pst.sex,
                        ps.date_of_birth,
                        ps.date_of_sample_collection,
                        pst.eye,
                        pst.person_hash,
                        pst.age
                '''
            else:
                # Anonymized export
                base_query = '''
                    SELECT 
                        ps.patient_id,
                        pst.person_hash,
                        pst.sex,
                        pst.eye,
                        pst.age
                '''

            # Add ocular conditions if requested
            if include_conditions:
                base_query += ''',
                    oc.lens_status,
                    oc.locs_iii_no,
                    oc.locs_iii_nc,
                    oc.locs_iii_c,
                    oc.locs_iii_p,
                    oc.iol_type,
                    oc.etiology_aphakia,
                    oc.glaucoma,
                    oc.oht_or_pac,
                    oc.etiology_glaucoma,
                    oc.steroid_responder,
                    oc.pxs,
                    oc.pds,
                    oc.diabetic_retinopathy,
                    oc.stage_diabetic_retinopathy,
                    oc.stage_npdr,
                    oc.stage_pdr,
                    oc.macular_edema,
                    oc.etiology_macular_edema,
                    oc.macular_degeneration_dystrophy,
                    oc.etiology_macular_deg_dyst,
                    oc.stage_amd,
                    oc.exudation_amd,
                    oc.stage_other_macular_deg,
                    oc.exudation_other_macular_deg,
                    oc.macular_hole_vmt,
                    oc.etiology_mh_vmt,
                    oc.cause_secondary_mh_vmt,
                    oc.treatment_status_mh_vmt,
                    oc.epiretinal_membrane,
                    oc.etiology_erm,
                    oc.cause_secondary_erm,
                    oc.treatment_status_erm,
                    oc.retinal_detachment,
                    oc.etiology_rd,
                    oc.treatment_status_rd,
                    oc.pvr,
                    oc.vitreous_haemorrhage_opacification,
                    oc.etiology_vitreous_haemorrhage
                '''

            base_query += '''
                FROM patients_sensitive ps
                JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
            '''

            if include_conditions:
                base_query += ' LEFT JOIN ocular_conditions oc ON ps.patient_id = oc.patient_id'

            base_query += ' WHERE 1=1'

            params = []

            # Add date filters
            if date_from:
                base_query += ' AND ps.date_of_sample_collection >= %s'
                params.append(date_from)
            if date_to:
                base_query += ' AND ps.date_of_sample_collection <= %s'
                params.append(date_to)

            # Add patient filters
            filter_clause, filter_params = build_filter_clause(request.form)
            base_query += filter_clause
            params.extend(filter_params)

            base_query += ' ORDER BY ps.patient_id'

            cur.execute(base_query, params)
            patients_data = cur.fetchall()

            # ============================================================
            # STEP 3: Preload all patient-related data for performance
            # ============================================================

            patient_ids = [p['patient_id'] for p in patients_data]

            # Preload other ocular conditions
            patient_ocular_conditions = {}
            if include_other_conditions and patient_ids:
                cur.execute('''
                    SELECT patient_id, icd10_code, eye 
                    FROM other_ocular_conditions 
                    WHERE patient_id = ANY(%s)
                ''', (patient_ids,))
                for row in cur.fetchall():
                    if row['patient_id'] not in patient_ocular_conditions:
                        patient_ocular_conditions[row['patient_id']] = []
                    patient_ocular_conditions[row['patient_id']].append(row)

            # Preload surgeries
            patient_surgeries = {}
            if include_surgeries and patient_ids:
                cur.execute('''
                    SELECT patient_id, surgery_code, eye 
                    FROM previous_ocular_surgeries 
                    WHERE patient_id = ANY(%s)
                ''', (patient_ids,))
                for row in cur.fetchall():
                    if row['patient_id'] not in patient_surgeries:
                        patient_surgeries[row['patient_id']] = []
                    patient_surgeries[row['patient_id']].append(row)

            # Preload systemic conditions
            patient_systemic = {}
            if include_systemic and patient_ids:
                cur.execute('''
                    SELECT patient_id, icd10_code 
                    FROM systemic_conditions 
                    WHERE patient_id = ANY(%s)
                ''', (patient_ids,))
                for row in cur.fetchall():
                    if row['patient_id'] not in patient_systemic:
                        patient_systemic[row['patient_id']] = []
                    patient_systemic[row['patient_id']].append(row)

            # Preload ocular medications
            patient_ocular_meds = {}
            if include_medications and patient_ids:
                cur.execute('''
                    SELECT patient_id, generic_name, eye, last_application_days 
                    FROM ocular_medications 
                    WHERE patient_id = ANY(%s)
                ''', (patient_ids,))
                for row in cur.fetchall():
                    if row['patient_id'] not in patient_ocular_meds:
                        patient_ocular_meds[row['patient_id']] = []
                    patient_ocular_meds[row['patient_id']].append(row)

            # Preload systemic medications
            patient_systemic_meds = {}
            if include_medications and patient_ids:
                cur.execute('''
                    SELECT patient_id, generic_name, last_application_days 
                    FROM systemic_medications 
                    WHERE patient_id = ANY(%s)
                ''', (patient_ids,))
                for row in cur.fetchall():
                    if row['patient_id'] not in patient_systemic_meds:
                        patient_systemic_meds[row['patient_id']] = []
                    patient_systemic_meds[row['patient_id']].append(row)

            # ============================================================
            # STEP 4: Build column headers (BINARY FORMAT)
            # ============================================================

            # Helper function to make safe column names
            def make_safe_column_name(name):
                """Convert any name to safe column name"""
                safe = str(name).lower()
                safe = safe.replace(' ', '_')
                safe = safe.replace('/', '_')
                safe = safe.replace('-', '_')
                safe = safe.replace('.', '_')
                safe = safe.replace('(', '')
                safe = safe.replace(')', '')
                safe = safe.replace('+', '_')
                safe = ''.join(c if c.isalnum() or c == '_' else '' for c in safe)
                # Ensure doesn't start with number
                if safe and safe[0].isdigit():
                    safe = 'x_' + safe
                return safe

            # Start with base columns
            if data_type == 'sensitive' and session.get('role') == 'Administrator':
                final_columns = [
                    'patient_id', 'patient_name', 'mbo', 'sex', 'date_of_birth',
                    'date_of_sample_collection', 'eye', 'person_hash', 'age'
                ]
            else:
                final_columns = ['patient_id', 'person_hash', 'sex', 'eye', 'age']

            # Add main condition columns if included
            if include_conditions:
                final_columns.extend([
                    'lens_status', 'locs_iii_no', 'locs_iii_nc', 'locs_iii_c', 'locs_iii_p',
                    'iol_type', 'etiology_aphakia', 'glaucoma', 'oht_or_pac', 'etiology_glaucoma',
                    'steroid_responder', 'pxs', 'pds', 'diabetic_retinopathy', 'stage_diabetic_retinopathy',
                    'stage_npdr', 'stage_pdr', 'macular_edema', 'etiology_macular_edema',
                    'macular_degeneration_dystrophy', 'etiology_macular_deg_dyst', 'stage_amd',
                    'exudation_amd', 'stage_other_macular_deg', 'exudation_other_macular_deg',
                    'macular_hole_vmt', 'etiology_mh_vmt', 'cause_secondary_mh_vmt',
                    'treatment_status_mh_vmt', 'epiretinal_membrane', 'etiology_erm',
                    'cause_secondary_erm', 'treatment_status_erm', 'retinal_detachment',
                    'etiology_rd', 'treatment_status_rd', 'pvr', 'vitreous_haemorrhage_opacification',
                    'etiology_vitreous_haemorrhage'
                ])

            # Add binary columns for other ocular conditions
            if include_other_conditions:
                for code in all_ocular_codes:
                    safe_code = make_safe_column_name(code)
                    final_columns.append(f'other_ocular_{safe_code}')
                    final_columns.append(f'other_ocular_{safe_code}_eye')

            # Add binary columns for surgeries
            if include_surgeries:
                for surgery in all_surgeries:
                    safe_surgery = make_safe_column_name(surgery)
                    final_columns.append(f'surgery_{safe_surgery}')
                    final_columns.append(f'surgery_{safe_surgery}_eye')

            # Add binary columns for systemic conditions
            if include_systemic:
                for code in all_systemic_codes:
                    safe_code = make_safe_column_name(code)
                    final_columns.append(f'systemic_{safe_code}')

            # Add binary columns for ocular medications
            if include_medications:
                for med in all_medications:
                    safe_med = make_safe_column_name(med)
                    final_columns.append(f'ocular_med_{safe_med}')
                    final_columns.append(f'ocular_med_{safe_med}_eye')
                    final_columns.append(f'ocular_med_{safe_med}_days')

            # Add binary columns for systemic medications
            if include_medications:
                for med in all_medications:
                    safe_med = make_safe_column_name(med)
                    final_columns.append(f'systemic_med_{safe_med}')
                    final_columns.append(f'systemic_med_{safe_med}_days')

            # ============================================================
            # STEP 5: Build export data with binary values
            # ============================================================

            export_data = []

            for patient in patients_data:
                # Initialize row with all columns set to default values
                row = {}

                # Fill base patient data
                for col in final_columns:
                    if col in patient:
                        value = patient[col]
                        # Convert dates to strings
                        if isinstance(value, (date, datetime)):
                            row[col] = value.strftime('%Y-%m-%d')
                        else:
                            row[col] = value
                    elif col.endswith('_eye'):
                        row[col] = 'ND'
                    elif col.endswith('_days'):
                        row[col] = 'ND'
                    elif col.startswith('other_ocular_') or col.startswith('surgery_') or \
                            col.startswith('systemic_') or col.startswith('ocular_med_') or \
                            col.startswith('systemic_med_'):
                        # Binary columns default to 0
                        if not col.endswith('_eye') and not col.endswith('_days'):
                            row[col] = 0
                        else:
                            row[col] = 'ND'
                    else:
                        row[col] = ''

                # Fill other ocular conditions (BINARY)
                if include_other_conditions:
                    for cond in patient_ocular_conditions.get(patient['patient_id'], []):
                        safe_code = make_safe_column_name(cond['icd10_code'])
                        row[f'other_ocular_{safe_code}'] = 1
                        row[f'other_ocular_{safe_code}_eye'] = cond['eye']

                # Fill surgeries (BINARY)
                if include_surgeries:
                    for surgery in patient_surgeries.get(patient['patient_id'], []):
                        safe_surgery = make_safe_column_name(surgery['surgery_code'])
                        row[f'surgery_{safe_surgery}'] = 1
                        row[f'surgery_{safe_surgery}_eye'] = surgery['eye']

                # Fill systemic conditions (BINARY)
                if include_systemic:
                    for cond in patient_systemic.get(patient['patient_id'], []):
                        safe_code = make_safe_column_name(cond['icd10_code'])
                        row[f'systemic_{safe_code}'] = 1

                # Fill ocular medications (BINARY)
                if include_medications:
                    for med in patient_ocular_meds.get(patient['patient_id'], []):
                        safe_med = make_safe_column_name(med['generic_name'])
                        row[f'ocular_med_{safe_med}'] = 1
                        row[f'ocular_med_{safe_med}_eye'] = med['eye']
                        row[f'ocular_med_{safe_med}_days'] = med['last_application_days']

                # Fill systemic medications (BINARY)
                if include_medications:
                    for med in patient_systemic_meds.get(patient['patient_id'], []):
                        safe_med = make_safe_column_name(med['generic_name'])
                        row[f'systemic_med_{safe_med}'] = 1
                        row[f'systemic_med_{safe_med}_days'] = med['last_application_days']

                export_data.append(row)

            # ============================================================
            # STEP 6: Generate export file
            # ============================================================

            if export_format == 'csv':
                # Generate CSV
                output = io.StringIO()
                if export_data:
                    writer = csv.DictWriter(output, fieldnames=final_columns, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(export_data)

                from flask import Response
                filename_type = 'sensitive' if data_type == 'sensitive' else 'anonymized'
                return Response(
                    output.getvalue(),
                    mimetype='text/csv',
                    headers={
                        'Content-Disposition': f'attachment; filename=raman_export_binary_{filename_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                    }
                )

            elif export_format == 'excel':
                # Generate Excel file
                try:
                    from openpyxl import Workbook
                    from openpyxl.styles import Font, PatternFill, Alignment
                    from openpyxl.utils import get_column_letter

                    wb = Workbook()
                    ws = wb.active
                    ws.title = "Patient Data"

                    if export_data:
                        # Write headers
                        header_fill = PatternFill(start_color="3498db", end_color="3498db", fill_type="solid")
                        header_font = Font(bold=True, color="FFFFFF")

                        for col_idx, fieldname in enumerate(final_columns, 1):
                            cell = ws.cell(row=1, column=col_idx, value=fieldname)
                            cell.fill = header_fill
                            cell.font = header_font
                            cell.alignment = Alignment(horizontal='center')

                        # Write data
                        for row_idx, data_row in enumerate(export_data, 2):
                            for col_idx, fieldname in enumerate(final_columns, 1):
                                value = data_row.get(fieldname, '')
                                ws.cell(row=row_idx, column=col_idx, value=value)

                        # Auto-adjust column widths
                        for col_idx in range(1, len(final_columns) + 1):
                            ws.column_dimensions[get_column_letter(col_idx)].width = 15

                    # Save to BytesIO
                    excel_output = io.BytesIO()
                    wb.save(excel_output)
                    excel_output.seek(0)

                    from flask import Response
                    filename_type = 'sensitive' if data_type == 'sensitive' else 'anonymized'
                    return Response(
                        excel_output.getvalue(),
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={
                            'Content-Disposition': f'attachment; filename=raman_export_binary_{filename_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                        }
                    )

                except ImportError:
                    flash('Excel export requires openpyxl. Please run: pip install openpyxl', 'error')
                    return redirect(url_for('export_data'))

        cur.close()
        conn.close()
        return render_template('export_data.html', stats=stats)

    except Exception as e:
        flash(f'Error with export: {str(e)}', 'error')
        if conn:
            conn.close()
        # Return proper stats structure even on error
        return render_template('export_data.html',
                               stats={'total_patients': 0, 'gender': {'M': 0, 'F': 0}, 'age_distribution': []})


# Settings Routes

@app.route('/settings')
@admin_required
def settings():
    """Settings page"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('settings.html', stats={})

    try:
        cur = conn.cursor()

        # Get counts for display
        cur.execute('SELECT COUNT(*) FROM icd10_ocular_conditions WHERE active = TRUE')
        ocular_icd10 = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM icd10_systemic_conditions WHERE active = TRUE')
        systemic_icd10 = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM medications WHERE active = TRUE')
        medications = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM surgeries WHERE active = TRUE')
        surgeries = cur.fetchone()[0]

        stats = {
            'ocular_icd10': ocular_icd10,
            'systemic_icd10': systemic_icd10,
            'medications': medications,
            'surgeries': surgeries
        }

        cur.close()
        conn.close()

        return render_template('settings.html', stats=stats)
    except Exception as e:
        flash(f'Error loading settings: {str(e)}', 'error')
        if conn:
            conn.close()
        return render_template('settings.html', stats={})


@app.route('/settings/icd10-ocular')
@admin_required
def settings_icd10_ocular():
    """Manage ICD-10 ocular conditions"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('settings'))

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM icd10_ocular_conditions ORDER BY code')
        codes = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('settings_icd10_ocular.html', codes=codes)
    except Exception as e:
        flash(f'Error loading ICD-10 codes: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('settings'))


@app.route('/settings/icd10-systemic')
@admin_required
def settings_icd10_systemic():
    """Manage ICD-10 systemic conditions"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('settings'))

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM icd10_systemic_conditions ORDER BY code')
        codes = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('settings_icd10_systemic.html', codes=codes)
    except Exception as e:
        flash(f'Error loading ICD-10 codes: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('settings'))


@app.route('/settings/medications')
@admin_required
def settings_medications():
    """Manage medications"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('settings'))

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM medications ORDER BY trade_name')
        medications = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('settings_medications.html', medications=medications)
    except Exception as e:
        flash(f'Error loading medications: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('settings'))


@app.route('/settings/surgeries')
@admin_required
def settings_surgeries():
    """Manage surgeries"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('settings'))

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM surgeries ORDER BY code')
        surgeries = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('settings_surgeries.html', surgeries=surgeries)
    except Exception as e:
        flash(f'Error loading surgeries: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('settings'))


# User Management Routes

@app.route('/user-management')
@admin_required
def user_management():
    """Manage users"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('user_management.html', users=[], stats={})

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get all users
        cur.execute('SELECT * FROM users ORDER BY user_id')
        users = cur.fetchall()

        # Get statistics
        cur.execute('SELECT COUNT(*) as total FROM users')
        total_users = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'Administrator'")
        administrators = cur.fetchone()['count']

        cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'Staff'")
        staff = cur.fetchone()['count']

        stats = {
            'total_users': total_users,
            'administrators': administrators,
            'staff': staff
        }

        cur.close()
        conn.close()

        return render_template('user_management.html', users=users, stats=stats)
    except Exception as e:
        flash(f'Error loading users: {str(e)}', 'error')
        if conn:
            conn.close()
        return render_template('user_management.html', users=[], stats={})


@app.route('/create-user', methods=['POST'])
@admin_required
def create_user():
    """Create new user"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('user_management'))

    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        cur = conn.cursor()
        cur.execute('''
            INSERT INTO users (username, password_hash, email, role)
            VALUES (%s, %s, %s, %s)
        ''', (username, password_hash, email, role))
        conn.commit()
        cur.close()
        conn.close()

        flash(f'User {username} created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating user: {str(e)}', 'error')
        if conn:
            conn.rollback()
            conn.close()

    return redirect(url_for('user_management'))


@app.route('/update-user', methods=['POST'])
@admin_required
def update_user():
    """Update user"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('user_management'))

    try:
        user_id = request.form.get('user_id')
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')

        cur = conn.cursor()

        if password:
            password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
            cur.execute('''
                UPDATE users
                SET username = %s, email = %s, role = %s, password_hash = %s
                WHERE user_id = %s
            ''', (username, email, role, password_hash, user_id))
        else:
            cur.execute('''
                UPDATE users
                SET username = %s, email = %s, role = %s
                WHERE user_id = %s
            ''', (username, email, role, user_id))

        conn.commit()
        cur.close()
        conn.close()

        flash(f'User {username} updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating user: {str(e)}', 'error')
        if conn:
            conn.rollback()
            conn.close()

    return redirect(url_for('user_management'))


@app.route('/delete-user', methods=['POST'])
@admin_required
def delete_user():
    """Delete user"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('user_management'))

    try:
        user_id = request.form.get('user_id')

        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE user_id = %s', (user_id,))
        conn.commit()
        cur.close()
        conn.close()

        flash('User deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting user: {str(e)}', 'error')
        if conn:
            conn.rollback()
            conn.close()

    return redirect(url_for('user_management'))


@app.route('/reset-user-password', methods=['POST'])
@admin_required
def reset_user_password():
    """Reset user password to default"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('user_management'))

    try:
        user_id = request.form.get('user_id')
        default_password = 'password123'
        password_hash = bcrypt.generate_password_hash(default_password).decode('utf-8')

        cur = conn.cursor()
        cur.execute('UPDATE users SET password_hash = %s WHERE user_id = %s', (password_hash, user_id))
        conn.commit()
        cur.close()
        conn.close()

        flash(f'Password reset to: {default_password}', 'success')
    except Exception as e:
        flash(f'Error resetting password: {str(e)}', 'error')
        if conn:
            conn.rollback()
            conn.close()

    return redirect(url_for('user_management'))


# API Routes for Managing Reference Data

@app.route('/api/icd10-ocular', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_icd10_ocular():
    """API for managing ICD-10 ocular conditions"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'GET':
            cur.execute('SELECT * FROM icd10_ocular_conditions ORDER BY code')
            codes = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify(codes)

        elif request.method == 'POST':
            data = request.get_json()
            cur.execute('''
                INSERT INTO icd10_ocular_conditions (code, description, category, active)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            ''', (data['code'], data['description'], data.get('category', ''), data.get('active', True)))
            new_code = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(new_code), 201

        elif request.method == 'PUT':
            data = request.get_json()
            cur.execute('''
                UPDATE icd10_ocular_conditions
                SET description = %s, category = %s, active = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
            ''', (data['description'], data.get('category', ''), data.get('active', True), data['id']))
            updated_code = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(updated_code)

        elif request.method == 'DELETE':
            data = request.get_json()
            cur.execute('''
                UPDATE icd10_ocular_conditions
                SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (data['id'],))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'success': True})

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/icd10-systemic', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_icd10_systemic():
    """API for managing ICD-10 systemic conditions"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'GET':
            cur.execute('SELECT * FROM icd10_systemic_conditions ORDER BY code')
            codes = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify(codes)

        elif request.method == 'POST':
            data = request.get_json()
            cur.execute('''
                INSERT INTO icd10_systemic_conditions (code, description, category, active)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            ''', (data['code'], data['description'], data.get('category', ''), data.get('active', True)))
            new_code = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(new_code), 201

        elif request.method == 'PUT':
            data = request.get_json()
            cur.execute('''
                UPDATE icd10_systemic_conditions
                SET description = %s, category = %s, active = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
            ''', (data['description'], data.get('category', ''), data.get('active', True), data['id']))
            updated_code = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(updated_code)

        elif request.method == 'DELETE':
            data = request.get_json()
            cur.execute('''
                UPDATE icd10_systemic_conditions
                SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (data['id'],))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'success': True})

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/medications', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_medications():
    """API for managing medications"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'GET':
            cur.execute('SELECT * FROM medications ORDER BY trade_name')
            medications = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify(medications)

        elif request.method == 'POST':
            data = request.get_json()
            cur.execute('''
                INSERT INTO medications (trade_name, generic_name, medication_type, active)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            ''', (
                data['trade_name'], data['generic_name'], data.get('medication_type', 'Both'),
                data.get('active', True)))
            new_medication = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(new_medication), 201

        elif request.method == 'PUT':
            data = request.get_json()
            cur.execute('''
                UPDATE medications
                SET trade_name = %s, generic_name = %s, medication_type = %s, 
                    active = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
            ''', (data['trade_name'], data['generic_name'], data.get('medication_type', 'Both'),
                  data.get('active', True), data['id']))
            updated_medication = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(updated_medication)

        elif request.method == 'DELETE':
            data = request.get_json()
            cur.execute('''
                UPDATE medications
                SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (data['id'],))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'success': True})

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/surgeries', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_surgeries():
    """API for managing surgeries"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if request.method == 'GET':
            cur.execute('SELECT * FROM surgeries ORDER BY code')
            surgeries = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify(surgeries)

        elif request.method == 'POST':
            data = request.get_json()
            cur.execute('''
                INSERT INTO surgeries (code, description, category, active)
                VALUES (%s, %s, %s, %s)
                RETURNING *
            ''', (data['code'], data['description'], data.get('category', ''), data.get('active', True)))
            new_surgery = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(new_surgery), 201

        elif request.method == 'PUT':
            data = request.get_json()
            cur.execute('''
                UPDATE surgeries
                SET description = %s, category = %s, active = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING *
            ''', (data['description'], data.get('category', ''), data.get('active', True), data['id']))
            updated_surgery = cur.fetchone()
            conn.commit()
            cur.close()
            conn.close()
            return jsonify(updated_surgery)

        elif request.method == 'DELETE':
            data = request.get_json()
            cur.execute('''
                UPDATE surgeries
                SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (data['id'],))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({'success': True})

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/check_patient_id/<int:patient_id>')
@login_required
def check_patient_id(patient_id):
    """Check if a patient ID is available"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error', 'available': False}), 500

    try:
        cur = conn.cursor()
        # Check if the patient_id exists in the sensitive table
        cur.execute("SELECT patient_id FROM patients_sensitive WHERE patient_id = %s", (patient_id,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return jsonify({'available': not exists, 'patient_id': patient_id})
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'error': str(e), 'available': False}), 500


@app.route('/api/next_available_patient_id')
@login_required
def api_next_available_patient_id():
    """API endpoint to get the next available patient ID"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error', 'next_id': STARTING_PATIENT_ID}), 500

    try:
        cur = conn.cursor()
        # Get the maximum patient_id from the database
        cur.execute("SELECT MAX(patient_id) FROM patients_sensitive")
        result = cur.fetchone()
        max_id = result[0] if result[0] is not None else (STARTING_PATIENT_ID - 1)

        # Next ID is max + 1, but ensure it's at least STARTING_PATIENT_ID
        next_id = max(max_id + 1, STARTING_PATIENT_ID)

        cur.close()
        conn.close()
        return jsonify({'next_id': next_id})
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'error': str(e), 'next_id': STARTING_PATIENT_ID}), 500


@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = get_db_connection()
        if conn:
            conn.close()
            return {'status': 'healthy'}, 200
        return {'status': 'unhealthy'}, 503
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 503


# Application Initialization and Startup

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("RAMAN MEDICAL RESEARCH DATABASE - Starting Up")
    print("=" * 60 + "\n")

    # Step 1: Check/Create database
    print("Step 1: Checking database existence...")
    if not create_database_if_not_exists():
        print("\n✗ Failed to create/access database. Exiting.")
        exit(1)

    # Step 2: Initialize tables and reference data
    print("\nStep 2: Initializing database tables and reference data...")
    if not init_database():
        print("\n✗ Warning: Database initialization had issues")
        print("The application may not work correctly.\n")
    else:
        print("\n✓ Database is ready!")

    # Step 3: Start the Flask application
    print("\n" + "=" * 60)
    print("Starting Flask application on http://0.0.0.0:5000")
    print("=" * 60 + "\n")

    app.run(host='0.0.0.0', port=5000, debug=False)
