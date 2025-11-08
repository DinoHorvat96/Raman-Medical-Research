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
            ''', ('Admin', admin_password, 'None', 'Administrator'))
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
        lens_status = request.form.get('lens_status')
        locs_iii_no = request.form.get('locs_no') if lens_status == 'Phakic' else None
        locs_iii_nc = request.form.get('locs_nc') if lens_status == 'Phakic' else None
        locs_iii_c = request.form.get('locs_c') if lens_status == 'Phakic' else None
        locs_iii_p = request.form.get('locs_p') if lens_status == 'Phakic' else None
        iol_type = request.form.get('iol_type') if lens_status == 'Pseudophakic' else None
        etiology_aphakia = request.form.get('aphakia_etiology') if lens_status == 'Aphakic' else None

        glaucoma = request.form.get('glaucoma')
        oht_or_pac = request.form.get('oht_or_pac') if glaucoma == '0' else None
        etiology_glaucoma = request.form.get('etiology_glaucoma') if glaucoma == '1' else None
        steroid_responder = request.form.get('steroid_responder')
        pxs = request.form.get('pxs')
        pds = request.form.get('pds')

        diabetic_retinopathy = request.form.get('diabetic_retinopathy')
        stage_diabetic_retinopathy = request.form.get(
            'dr_stage') if diabetic_retinopathy == '1' else None
        stage_npdr = request.form.get('npdr_stage') if stage_diabetic_retinopathy == 'NPDR' else None
        stage_pdr = request.form.get('pdr_stage') if stage_diabetic_retinopathy == 'PDR' else None

        macular_edema = request.form.get('macular_edema')
        etiology_macular_edema = request.form.get('me_etiology') if macular_edema == '1' else None

        macular_degeneration_dystrophy = request.form.get('macular_degeneration')
        etiology_macular_deg_dyst = request.form.get('md_etiology') if macular_degeneration_dystrophy == '1' else None
        stage_amd = request.form.get('amd_stage') if etiology_macular_deg_dyst == 'AMD' else None
        exudation_amd = request.form.get('amd_exudation') if stage_amd in ['nAMD', 'nAMD+GA', 'ND'] else None
        stage_other_macular_deg = request.form.get('other_md_stage') if etiology_macular_deg_dyst == 'Other' else None
        exudation_other_macular_deg = request.form.get(
            'other_md_exudation') if etiology_macular_deg_dyst == 'Other' else None

        macular_hole_vmt = request.form.get('mh_vmt')
        etiology_mh_vmt = request.form.get('mh_vmt_etiology') if macular_hole_vmt == '1' else None
        cause_secondary_mh_vmt = request.form.get('secondary_mh_vmt_cause') if etiology_mh_vmt == 'Secondary' else None
        treatment_status_mh_vmt = request.form.get('mh_vmt_treatment_status') if macular_hole_vmt == '1' else None

        epiretinal_membrane = request.form.get('epiretinal_membrane')
        etiology_erm = request.form.get('erm_etiology') if epiretinal_membrane == '1' else None
        cause_secondary_erm = request.form.get('secondary_erm_cause') if etiology_erm == 'Secondary' else None
        treatment_status_erm = request.form.get('erm_treatment_status') if epiretinal_membrane == '1' else None

        retinal_detachment = request.form.get('retinal_detachment')
        etiology_rd = request.form.get('rd_etiology') if retinal_detachment not in ['0', 'ND'] else None
        treatment_status_rd = request.form.get('rd_treatment_status') if retinal_detachment not in ['0', 'ND'] else None
        pvr = request.form.get('pvr') if retinal_detachment not in ['0', 'ND'] else None

        vitreous_haemorrhage_opacification = request.form.get('vitreous_opacification')
        etiology_vitreous_haemorrhage = request.form.get(
            'vh_etiology') if vitreous_haemorrhage_opacification == 'Vitreous haemorrhage' else None

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

@app.route('/validate-data')
@staff_or_admin_required
def validate_data():
    """Search and list patients for validation"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('validate_data.html', patients=[])

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get search parameters
        search_type = request.args.get('type', 'id')
        search_query = request.args.get('q', '')

        if search_query:
            if search_type == 'id':
                # Search by patient ID
                cur.execute('''
                    SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, ps.date_of_sample_collection,
                           pst.sex, pst.eye
                    FROM patients_sensitive ps
                    JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                    WHERE CAST(ps.patient_id AS TEXT) LIKE %s
                    ORDER BY ps.patient_id DESC
                    LIMIT 20
                ''', (f'%{search_query}%',))
            elif search_type == 'name':
                # Search by name
                cur.execute('''
                    SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, ps.date_of_sample_collection,
                           pst.sex, pst.eye
                    FROM patients_sensitive ps
                    JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                    WHERE LOWER(ps.patient_name) LIKE LOWER(%s)
                    ORDER BY ps.patient_id DESC
                    LIMIT 20
                ''', (f'%{search_query}%',))
            elif search_type == 'mbo':
                # Search by MBO
                cur.execute('''
                    SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, ps.date_of_sample_collection,
                           pst.sex, pst.eye
                    FROM patients_sensitive ps
                    JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                    WHERE ps.mbo LIKE %s
                    ORDER BY ps.patient_id DESC
                    LIMIT 20
                ''', (f'%{search_query}%',))
            patients = cur.fetchall()
        else:
            # Show 20 most recent patients if no search query
            cur.execute('''
                SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, ps.date_of_sample_collection,
                       pst.sex, pst.eye
                FROM patients_sensitive ps
                JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                ORDER BY ps.patient_id DESC
                LIMIT 20
            ''')
            patients = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('validate_data.html',
                               patients=patients,
                               search_type=search_type,
                               search_query=search_query)
    except Exception as e:
        flash(f'Error searching patients: {str(e)}', 'error')
        if conn:
            conn.close()
        return render_template('validate_data.html', patients=[])


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
    """Export statistical data with role-based access and proper column ordering"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('export_data.html', stats={})

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
        gender = {row['sex']: row['count'] for row in gender_stats}

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

            # Build the main query - with proper column ordering
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
                # Anonymized export - order matches form layout (excluding sensitive fields)
                base_query = '''
                    SELECT 
                        ps.patient_id,
                        pst.person_hash,
                        pst.sex,
                        pst.eye,
                        pst.age
                '''

            # Add ocular conditions if requested - in order of appearance in form
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
            if date_from:
                base_query += ' AND ps.date_of_sample_collection >= %s'
                params.append(date_from)
            if date_to:
                base_query += ' AND ps.date_of_sample_collection <= %s'
                params.append(date_to)

            base_query += ' ORDER BY ps.patient_id'

            cur.execute(base_query, params)
            patients_data = cur.fetchall()

            # Define column order - this ensures consistent ordering in exports
            if data_type == 'sensitive' and session.get('role') == 'Administrator':
                # Order matching form: ID, Name, MBO, Sex, DOB, DoSC, Eye, Hash, Age, then conditions
                base_columns = [
                    'patient_id', 'patient_name', 'mbo', 'sex', 'date_of_birth',
                    'date_of_sample_collection', 'eye', 'person_hash', 'age'
                ]
            else:
                # Order for anonymized: ID, Hash, Sex, Eye, Age, then conditions
                base_columns = ['patient_id', 'person_hash', 'sex', 'eye', 'age']

            # Add condition columns in order if included
            condition_columns = []
            if include_conditions:
                condition_columns = [
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
                ]

            # Convert to list of dicts and add dynamic columns
            export_data = []
            dynamic_columns = {
                'other_conditions': [],
                'surgeries': [],
                'systemic': [],
                'ocular_meds': [],
                'systemic_meds': []
            }

            for row in patients_data:
                patient_dict = dict(row)

                # Add other ocular conditions if requested
                if include_other_conditions:
                    cur.execute('''
                        SELECT icd10_code, eye 
                        FROM other_ocular_conditions 
                        WHERE patient_id = %s
                        ORDER BY id
                    ''', (row['patient_id'],))
                    other_conds = cur.fetchall()

                    for idx, cond in enumerate(other_conds, 1):
                        col_name = f'other_ocular_condition_{idx}'
                        col_eye = f'other_ocular_condition_{idx}_eye'
                        patient_dict[col_name] = cond['icd10_code']
                        patient_dict[col_eye] = cond['eye']
                        if col_name not in dynamic_columns['other_conditions']:
                            dynamic_columns['other_conditions'].extend([col_name, col_eye])

                # Add surgeries if requested
                if include_surgeries:
                    cur.execute('''
                        SELECT surgery_code, eye 
                        FROM previous_ocular_surgeries 
                        WHERE patient_id = %s
                        ORDER BY id
                    ''', (row['patient_id'],))
                    surgeries = cur.fetchall()

                    for idx, surgery in enumerate(surgeries, 1):
                        col_name = f'surgery_{idx}'
                        col_eye = f'surgery_{idx}_eye'
                        patient_dict[col_name] = surgery['surgery_code']
                        patient_dict[col_eye] = surgery['eye']
                        if col_name not in dynamic_columns['surgeries']:
                            dynamic_columns['surgeries'].extend([col_name, col_eye])

                # Add systemic conditions if requested
                if include_systemic:
                    cur.execute('''
                        SELECT icd10_code 
                        FROM systemic_conditions 
                        WHERE patient_id = %s
                        ORDER BY id
                    ''', (row['patient_id'],))
                    sys_conds = cur.fetchall()

                    for idx, cond in enumerate(sys_conds, 1):
                        col_name = f'systemic_condition_{idx}'
                        patient_dict[col_name] = cond['icd10_code']
                        if col_name not in dynamic_columns['systemic']:
                            dynamic_columns['systemic'].append(col_name)

                # Add medications if requested
                if include_medications:
                    # Ocular medications
                    cur.execute('''
                        SELECT generic_name, eye, last_application_days 
                        FROM ocular_medications 
                        WHERE patient_id = %s
                        ORDER BY id
                    ''', (row['patient_id'],))
                    ocular_meds = cur.fetchall()

                    for idx, med in enumerate(ocular_meds, 1):
                        col_name = f'ocular_medication_{idx}'
                        col_eye = f'ocular_medication_{idx}_eye'
                        col_days = f'ocular_medication_{idx}_last_app_days'
                        patient_dict[col_name] = med['generic_name']
                        patient_dict[col_eye] = med['eye']
                        patient_dict[col_days] = med['last_application_days']
                        if col_name not in dynamic_columns['ocular_meds']:
                            dynamic_columns['ocular_meds'].extend([col_name, col_eye, col_days])

                    # Systemic medications
                    cur.execute('''
                        SELECT generic_name, last_application_days 
                        FROM systemic_medications 
                        WHERE patient_id = %s
                        ORDER BY id
                    ''', (row['patient_id'],))
                    sys_meds = cur.fetchall()

                    for idx, med in enumerate(sys_meds, 1):
                        col_name = f'systemic_medication_{idx}'
                        col_days = f'systemic_medication_{idx}_last_app_days'
                        patient_dict[col_name] = med['generic_name']
                        patient_dict[col_days] = med['last_application_days']
                        if col_name not in dynamic_columns['systemic_meds']:
                            dynamic_columns['systemic_meds'].extend([col_name, col_days])

                export_data.append(patient_dict)

            # Build final column order
            final_columns = base_columns + condition_columns

            # Add dynamic columns in logical order
            final_columns.extend(dynamic_columns['other_conditions'])
            final_columns.extend(dynamic_columns['surgeries'])
            final_columns.extend(dynamic_columns['systemic'])
            final_columns.extend(dynamic_columns['ocular_meds'])
            final_columns.extend(dynamic_columns['systemic_meds'])

            # Generate export file
            if export_format == 'csv':
                # Generate CSV with proper column order
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
                        'Content-Disposition': f'attachment; filename=raman_export_{filename_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                    }
                )

            elif export_format == 'excel':
                # Generate Excel file using openpyxl with proper column order
                try:
                    from openpyxl import Workbook
                    from openpyxl.styles import Font, PatternFill, Alignment
                    from openpyxl.utils import get_column_letter

                    wb = Workbook()
                    ws = wb.active
                    ws.title = "Patient Data"

                    if export_data:
                        # Write headers in proper order
                        header_fill = PatternFill(start_color="3498db", end_color="3498db", fill_type="solid")
                        header_font = Font(bold=True, color="FFFFFF")

                        for col_idx, fieldname in enumerate(final_columns, 1):
                            cell = ws.cell(row=1, column=col_idx, value=fieldname)
                            cell.fill = header_fill
                            cell.font = header_font
                            cell.alignment = Alignment(horizontal='center')

                        # Write data in proper order
                        for row_idx, data_row in enumerate(export_data, 2):
                            for col_idx, fieldname in enumerate(final_columns, 1):
                                value = data_row.get(fieldname, '')
                                # Convert dates to strings
                                if isinstance(value, (date, datetime)):
                                    value = value.strftime('%Y-%m-%d')
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
                            'Content-Disposition': f'attachment; filename=raman_export_{filename_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
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
        return render_template('export_data.html', stats={})


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

        cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'Patient'")
        patients = cur.fetchone()['count']

        stats = {
            'total_users': total_users,
            'administrators': administrators,
            'staff': staff,
            'patients': patients
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
