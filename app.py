import os
import hashlib
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_bcrypt import Bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
bcrypt = Bcrypt(app)

# Database configuration
DB_NAME = os.getenv('DB_NAME', 'raman_research')
DB_CONFIG = {
    'dbname': DB_NAME,
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}


def create_database_if_not_exists():
    """Create the database if it doesn't exist"""
    try:
        print(f"Attempting to connect to PostgreSQL server at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"Using user: {DB_CONFIG['user']}")

        conn = psycopg2.connect(
            dbname='postgres',
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cur.fetchone()

        if not exists:
            print(f"Database '{DB_NAME}' does not exist. Creating...")
            cur.execute(f'CREATE DATABASE {DB_NAME}')
            print(f"Database '{DB_NAME}' created successfully")
        else:
            print(f"Database '{DB_NAME}' already exists")

        cur.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"Error creating database: {e}")
        print(f"\nPlease create the database manually using:")
        print(f"  CREATE DATABASE {DB_NAME};")
        return False


def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None


def generate_person_hash(mbo):
    """Generate SHA-256 hash from MBO for anonymization"""
    if not mbo or mbo == '':
        return None
    return hashlib.sha256(mbo.encode()).hexdigest()


def calculate_age(date_of_birth, collection_date):
    """Calculate age at time of sample collection"""
    if not date_of_birth or not collection_date:
        return None

    if isinstance(date_of_birth, str):
        date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
    if isinstance(collection_date, str):
        collection_date = datetime.strptime(collection_date, '%Y-%m-%d').date()

    age = collection_date.year - date_of_birth.year
    if (collection_date.month, collection_date.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def init_database():
    """Initialize database with tables and default admin user"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()

        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                role VARCHAR(50) NOT NULL CHECK (role IN ('Patient', 'Staff', 'Administrator')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)

        # Patient ID sequence with custom start value
        cur.execute("""
            CREATE SEQUENCE IF NOT EXISTS patient_id_seq
            START WITH 1500
            INCREMENT BY 1
            MINVALUE 1
            MAXVALUE 99999
            CACHE 1
        """)

        # Sensitive patient data (protected)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patients_sensitive (
                patient_id INTEGER PRIMARY KEY CHECK (patient_id >= 1 AND patient_id <= 99999),
                patient_name VARCHAR(255) NOT NULL,
                mbo CHAR(9) NOT NULL,
                date_of_birth DATE NOT NULL,
                date_of_sample_collection DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER REFERENCES users(user_id)
            )
        """)

        # Statistical export data (anonymized)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS patients_statistical (
                patient_id INTEGER PRIMARY KEY REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                person_hash VARCHAR(64),
                age INTEGER,
                sex CHAR(1) CHECK (sex IN ('M', 'F')),
                eye VARCHAR(2) CHECK (eye IN ('L', 'R', 'ND'))
            )
        """)

        # Main ocular conditions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ocular_conditions (
                patient_id INTEGER PRIMARY KEY REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                lens_status VARCHAR(20) CHECK (lens_status IN ('Phakic', 'Pseudophakic', 'Aphakic', 'ND')),
                locs_iii_no VARCHAR(10),
                locs_iii_nc VARCHAR(10),
                locs_iii_c VARCHAR(10),
                locs_iii_p VARCHAR(10),
                iol_type VARCHAR(50),
                aphakia_etiology VARCHAR(50),
                glaucoma VARCHAR(2),
                oht_or_pac VARCHAR(10),
                glaucoma_etiology VARCHAR(50),
                steroid_responder VARCHAR(2),
                pxs VARCHAR(2),
                pds VARCHAR(2),
                diabetic_retinopathy VARCHAR(2),
                dr_stage VARCHAR(20),
                npdr_stage VARCHAR(20),
                pdr_stage VARCHAR(20),
                macular_edema VARCHAR(2),
                me_etiology VARCHAR(50),
                macular_degeneration VARCHAR(2),
                md_etiology VARCHAR(50),
                amd_stage VARCHAR(50),
                amd_exudation VARCHAR(2),
                other_md_stage VARCHAR(50),
                other_md_exudation VARCHAR(2),
                mh_vmt VARCHAR(2),
                mh_vmt_etiology VARCHAR(50),
                secondary_mh_vmt_cause TEXT,
                mh_vmt_treatment_status VARCHAR(50),
                epiretinal_membrane VARCHAR(2),
                erm_etiology VARCHAR(50),
                secondary_erm_cause TEXT,
                erm_treatment_status VARCHAR(50),
                retinal_detachment VARCHAR(50),
                rd_etiology VARCHAR(100),
                rd_treatment_status VARCHAR(100),
                pvr VARCHAR(2),
                vitreous_opacification VARCHAR(100),
                vh_etiology VARCHAR(100)
            )
        """)

        # Other ocular conditions (ICD-10) - one-to-many
        cur.execute("""
            CREATE TABLE IF NOT EXISTS other_ocular_conditions (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                icd10_code VARCHAR(20) NOT NULL,
                eye VARCHAR(10) CHECK (eye IN ('R', 'L', 'R+L', 'ND'))
            )
        """)

        # Previous ocular surgeries - one-to-many
        cur.execute("""
            CREATE TABLE IF NOT EXISTS previous_ocular_surgeries (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                surgery_code VARCHAR(50) NOT NULL,
                eye VARCHAR(10) CHECK (eye IN ('R', 'L', 'R+L', 'ND'))
            )
        """)

        # Systemic conditions (ICD-10) - one-to-many
        cur.execute("""
            CREATE TABLE IF NOT EXISTS systemic_conditions (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                icd10_code VARCHAR(20) NOT NULL
            )
        """)

        # Ocular medications - one-to-many
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ocular_medications (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                trade_name VARCHAR(255) NOT NULL,
                generic_name VARCHAR(255) NOT NULL,
                eye VARCHAR(10) CHECK (eye IN ('R', 'L', 'R+L', 'ND')),
                days_before_collection INTEGER CHECK (days_before_collection >= 0 AND days_before_collection <= 999)
            )
        """)

        # Systemic medications - one-to-many
        cur.execute("""
            CREATE TABLE IF NOT EXISTS systemic_medications (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER REFERENCES patients_sensitive(patient_id) ON DELETE CASCADE,
                trade_name VARCHAR(255) NOT NULL,
                generic_name VARCHAR(255) NOT NULL,
                days_before_collection INTEGER CHECK (days_before_collection >= 0 AND days_before_collection <= 999)
            )
        """)

        # Check if admin user exists
        cur.execute("SELECT user_id FROM users WHERE username = 'Admin'")
        if not cur.fetchone():
            hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
            cur.execute("""
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (%s, %s, %s, %s)
            """, ('Admin', hashed_password, 'Administrator', datetime.now()))
            print("Default admin user created: Admin / admin123")

        conn.commit()
        cur.close()
        print("Database initialized successfully")
        return True

    except psycopg2.Error as e:
        print(f"Database initialization error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# Authentication routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
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
            cur.execute("""
                SELECT user_id, username, password_hash, role, email
                FROM users
                WHERE username = %s
            """, (username,))

            user = cur.fetchone()

            if user and bcrypt.check_password_hash(user['password_hash'], password):
                cur.execute("""
                    UPDATE users
                    SET last_login = %s
                    WHERE user_id = %s
                """, (datetime.now(), user['user_id']))
                conn.commit()

                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']

                flash(f'Welcome, {user["username"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')

        except psycopg2.Error as e:
            print(f"Login error: {e}")
            flash('Login error occurred', 'error')
        finally:
            cur.close()
            conn.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('dashboard.html')


@app.route('/new-patient', methods=['GET', 'POST'])
def new_patient():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['Administrator', 'Staff']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        # Get next available patient ID
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT nextval('patient_id_seq')")
                next_id = cur.fetchone()[0]
                # Put the value back
                cur.execute("SELECT setval('patient_id_seq', %s, false)", (next_id,))
                conn.commit()
                cur.close()
                conn.close()
                return render_template('new_patient.html', next_patient_id=next_id)
            except:
                pass
        return render_template('new_patient.html', next_patient_id=1500)

    # Handle POST - save patient
    # This will be implemented in the next iteration
    flash('Patient creation functionality coming soon', 'info')
    return redirect(url_for('dashboard'))


@app.route('/api/check-patient-id/<int:patient_id>')
def check_patient_id(patient_id):
    """API endpoint to check if patient ID is available"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'available': False, 'error': 'Database connection error'})

    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM patients_sensitive WHERE patient_id = %s", (patient_id,))
        exists = cur.fetchone()
        cur.close()
        conn.close()

        return jsonify({'available': not bool(exists)})
    except psycopg2.Error as e:
        return jsonify({'available': False, 'error': str(e)})


if __name__ == '__main__':
    print("Checking database...")
    if create_database_if_not_exists():
        print("Initializing database tables...")
        init_database()
    else:
        print("Warning: Could not create/access database.")

    app.run(host='0.0.0.0', port=5000, debug=True)
