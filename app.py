import os
import hashlib
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_bcrypt import Bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import csv
import io

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


@app.route('/export-data', methods=['GET', 'POST'])
def export_data():
    """Export anonymized patient data for statistical analysis"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['Administrator', 'Staff']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # Get export parameters
        export_format = request.form.get('format', 'csv')
        include_conditions = request.form.get('include_conditions', 'off') == 'on'
        include_other_conditions = request.form.get('include_other_conditions', 'off') == 'on'
        include_medications = request.form.get('include_medications', 'off') == 'on'
        include_surgeries = request.form.get('include_surgeries', 'off') == 'on'
        include_systemic = request.form.get('include_systemic', 'off') == 'on'
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')

        # Generate the export
        export_file = generate_statistical_export(
            export_format,
            include_conditions,
            include_other_conditions,
            include_medications,
            include_surgeries,
            include_systemic,
            date_from,
            date_to
        )

        if export_file:
            return export_file
        else:
            flash('Error generating export', 'error')

    # Get summary statistics for display
    conn = get_db_connection()
    stats = {}
    if conn:
        try:
            cur = conn.cursor()

            # Total patients
            cur.execute("SELECT COUNT(*) FROM patients_sensitive")
            stats['total_patients'] = cur.fetchone()[0]

            # Gender distribution
            cur.execute("""
                SELECT sex, COUNT(*) 
                FROM patients_statistical 
                WHERE sex IN ('M', 'F')
                GROUP BY sex
            """)
            gender_stats = cur.fetchall()
            stats['gender'] = {row[0]: row[1] for row in gender_stats}

            # Age distribution
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN age < 18 THEN '<18'
                        WHEN age BETWEEN 18 AND 40 THEN '18-40'
                        WHEN age BETWEEN 41 AND 60 THEN '41-60'
                        WHEN age BETWEEN 61 AND 80 THEN '61-80'
                        ELSE '>80'
                    END as age_group,
                    COUNT(*) as count
                FROM patients_statistical
                WHERE age IS NOT NULL
                GROUP BY age_group
                ORDER BY age_group
            """)
            stats['age_distribution'] = cur.fetchall()

            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error getting statistics: {e}")
            if conn:
                conn.close()

    return render_template('export_data.html', stats=stats)


def generate_statistical_export(format_type='csv', include_conditions=True,
                                include_other_conditions=False,
                                include_medications=False, include_surgeries=False,
                                include_systemic=False, date_from=None, date_to=None):
    """Generate anonymized statistical export"""

    conn = get_db_connection()
    if not conn:
        return None

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Build the main query
        query = """
            SELECT 
                pst.person_hash,
                pst.age,
                pst.sex,
                pst.eye
        """

        tables = [
            "FROM patients_sensitive ps",
            "JOIN patients_statistical pst ON ps.patient_id = pst.patient_id"
        ]

        where_clauses = []
        params = []

        if include_conditions:
            query += """,
                oc.lens_status,
                oc.locs_iii_no, oc.locs_iii_nc, oc.locs_iii_c, oc.locs_iii_p,
                oc.iol_type, oc.aphakia_etiology,
                oc.glaucoma, oc.oht_or_pac, oc.glaucoma_etiology,
                oc.steroid_responder, oc.pxs, oc.pds,
                oc.diabetic_retinopathy, oc.dr_stage, oc.npdr_stage, oc.pdr_stage,
                oc.macular_edema, oc.me_etiology,
                oc.macular_degeneration, oc.md_etiology, oc.amd_stage, oc.amd_exudation,
                oc.other_md_stage, oc.other_md_exudation,
                oc.mh_vmt, oc.mh_vmt_etiology, oc.secondary_mh_vmt_cause, oc.mh_vmt_treatment_status,
                oc.epiretinal_membrane, oc.erm_etiology, oc.secondary_erm_cause, oc.erm_treatment_status,
                oc.retinal_detachment, oc.rd_etiology, oc.rd_treatment_status, oc.pvr,
                oc.vitreous_opacification, oc.vh_etiology
            """
            tables.append("LEFT JOIN ocular_conditions oc ON ps.patient_id = oc.patient_id")

        # Add date filters if provided
        if date_from:
            where_clauses.append("ps.date_of_sample_collection >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("ps.date_of_sample_collection <= %s")
            params.append(date_to)

        # Build final query
        query += " " + " ".join(tables)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY ps.patient_id"

        cur.execute(query, params)
        main_data = cur.fetchall()

        # Process additional data if needed
        additional_data = {}

        if include_other_conditions:
            cur.execute("""
                SELECT patient_id, icd10_code, eye 
                FROM other_ocular_conditions 
                ORDER BY patient_id, id
            """)
            other_conditions = cur.fetchall()
            for row in other_conditions:
                pid = row['patient_id']
                if pid not in additional_data:
                    additional_data[pid] = {}
                if 'other_ocular_conditions' not in additional_data[pid]:
                    additional_data[pid]['other_ocular_conditions'] = []
                additional_data[pid]['other_ocular_conditions'].append(f"{row['icd10_code']}_{row['eye']}")

        if include_surgeries:
            cur.execute("""
                SELECT patient_id, surgery_code, eye 
                FROM previous_ocular_surgeries 
                ORDER BY patient_id, id
            """)
            surgeries = cur.fetchall()
            for row in surgeries:
                pid = row['patient_id']
                if pid not in additional_data:
                    additional_data[pid] = {}
                if 'previous_surgeries' not in additional_data[pid]:
                    additional_data[pid]['previous_surgeries'] = []
                additional_data[pid]['previous_surgeries'].append(f"{row['surgery_code']}_{row['eye']}")

        if include_systemic:
            cur.execute("""
                SELECT patient_id, icd10_code 
                FROM systemic_conditions 
                ORDER BY patient_id, id
            """)
            systemic = cur.fetchall()
            for row in systemic:
                pid = row['patient_id']
                if pid not in additional_data:
                    additional_data[pid] = {}
                if 'systemic_conditions' not in additional_data[pid]:
                    additional_data[pid]['systemic_conditions'] = []
                additional_data[pid]['systemic_conditions'].append(row['icd10_code'])

        if include_medications:
            # Ocular medications
            cur.execute("""
                SELECT patient_id, generic_name, eye, days_before_collection 
                FROM ocular_medications 
                ORDER BY patient_id, id
            """)
            ocular_meds = cur.fetchall()
            for row in ocular_meds:
                pid = row['patient_id']
                if pid not in additional_data:
                    additional_data[pid] = {}
                if 'ocular_medications' not in additional_data[pid]:
                    additional_data[pid]['ocular_medications'] = []
                additional_data[pid]['ocular_medications'].append(
                    f"{row['generic_name']}_{row['eye']}_{row['days_before_collection']}"
                )

            # Systemic medications
            cur.execute("""
                SELECT patient_id, generic_name, days_before_collection 
                FROM systemic_medications 
                ORDER BY patient_id, id
            """)
            systemic_meds = cur.fetchall()
            for row in systemic_meds:
                pid = row['patient_id']
                if pid not in additional_data:
                    additional_data[pid] = {}
                if 'systemic_medications' not in additional_data[pid]:
                    additional_data[pid]['systemic_medications'] = []
                additional_data[pid]['systemic_medications'].append(
                    f"{row['generic_name']}_{row['days_before_collection']}"
                )

        cur.close()
        conn.close()

        if format_type == 'csv':
            # Create CSV in memory
            output = io.StringIO()

            if main_data:
                # Get all field names
                fieldnames = list(main_data[0].keys())

                # Add additional fields
                if additional_data:
                    all_additional_fields = set()
                    for patient_data in additional_data.values():
                        all_additional_fields.update(patient_data.keys())
                    fieldnames.extend(sorted(all_additional_fields))

                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()

                for row in main_data:
                    # Add additional data if exists
                    pid = row.get('patient_id')
                    if pid in additional_data:
                        for key, values in additional_data[pid].items():
                            row[key] = '; '.join(values)
                    writer.writerow(row)

            # Convert to bytes
            output.seek(0)
            mem = io.BytesIO()
            mem.write(output.getvalue().encode('utf-8-sig'))  # UTF-8 with BOM for Excel
            mem.seek(0)

            return send_file(
                mem,
                mimetype='text/csv',
                download_name=f'raman_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                as_attachment=True
            )

        elif format_type == 'excel':
            # For Excel export, we'll need openpyxl
            try:
                from openpyxl import Workbook
                from openpyxl.utils import get_column_letter

                wb = Workbook()
                ws = wb.active
                ws.title = "Patient Data"

                if main_data:
                    # Prepare headers
                    headers = list(main_data[0].keys())

                    # Add additional field headers
                    if additional_data:
                        all_additional_fields = set()
                        for patient_data in additional_data.values():
                            all_additional_fields.update(patient_data.keys())
                        headers.extend(sorted(all_additional_fields))

                    # Write headers
                    for col, header in enumerate(headers, 1):
                        ws.cell(row=1, column=col, value=header)

                    # Write data
                    for row_idx, row in enumerate(main_data, 2):
                        # Add main data
                        for col_idx, header in enumerate(headers, 1):
                            if header in row:
                                ws.cell(row=row_idx, column=col_idx, value=row[header])
                            else:
                                # Check additional data
                                pid = row.get('patient_id')
                                if pid in additional_data and header in additional_data[pid]:
                                    value = '; '.join(additional_data[pid][header])
                                    ws.cell(row=row_idx, column=col_idx, value=value)

                    # Auto-adjust column widths
                    for column in ws.columns:
                        max_length = 0
                        column = [cell for cell in column]
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)
                        ws.column_dimensions[get_column_letter(column[0].column)].width = adjusted_width

                # Save to memory
                excel_mem = io.BytesIO()
                wb.save(excel_mem)
                excel_mem.seek(0)

                return send_file(
                    excel_mem,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    download_name=f'raman_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
                    as_attachment=True
                )

            except ImportError:
                flash('openpyxl library not installed. Please install it for Excel export: pip install openpyxl',
                      'error')
                return None

    except Exception as e:
        print(f"Error generating export: {e}")
        if conn:
            conn.close()
        return None


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
    try:
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('new_patient'))

        cur = conn.cursor()

        # Extract form data
        patient_id = int(request.form.get('patient_id'))
        patient_name = request.form.get('patient_name')
        mbo = request.form.get('mbo')
        sex = request.form.get('sex')
        eye = request.form.get('eye')

        # Build dates
        dob_day = int(request.form.get('dob_day'))
        dob_month = int(request.form.get('dob_month'))
        dob_year = int(request.form.get('dob_year'))
        date_of_birth = date(dob_year, dob_month, dob_day)

        col_day = int(request.form.get('collection_day'))
        col_month = int(request.form.get('collection_month'))
        col_year = int(request.form.get('collection_year'))
        date_of_collection = date(col_year, col_month, col_day)

        # Check if patient ID already exists
        cur.execute("SELECT 1 FROM patients_sensitive WHERE patient_id = %s", (patient_id,))
        if cur.fetchone():
            flash('Patient ID already exists. Please choose a different ID.', 'error')
            return redirect(url_for('new_patient'))

        # Insert into patients_sensitive
        cur.execute("""
            INSERT INTO patients_sensitive 
            (patient_id, patient_name, mbo, date_of_birth, date_of_sample_collection, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (patient_id, patient_name, mbo, date_of_birth, date_of_collection, session['user_id']))

        # Insert into patients_statistical
        person_hash = generate_person_hash(mbo)
        age = calculate_age(date_of_birth, date_of_collection)

        cur.execute("""
            INSERT INTO patients_statistical 
            (patient_id, person_hash, age, sex, eye)
            VALUES (%s, %s, %s, %s, %s)
        """, (patient_id, person_hash, age, sex, eye))

        # Insert ocular conditions
        cur.execute("""
            INSERT INTO ocular_conditions (
                patient_id, lens_status, locs_iii_no, locs_iii_nc, locs_iii_c, locs_iii_p,
                iol_type, aphakia_etiology, glaucoma, oht_or_pac, glaucoma_etiology,
                steroid_responder, pxs, pds, diabetic_retinopathy, dr_stage, npdr_stage, pdr_stage,
                macular_edema, me_etiology, macular_degeneration, md_etiology, amd_stage, amd_exudation,
                other_md_stage, other_md_exudation, mh_vmt, mh_vmt_etiology, secondary_mh_vmt_cause,
                mh_vmt_treatment_status, epiretinal_membrane, erm_etiology, secondary_erm_cause,
                erm_treatment_status, retinal_detachment, rd_etiology, rd_treatment_status, pvr,
                vitreous_opacification, vh_etiology
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            patient_id,
            request.form.get('lens_status', 'ND'),
            request.form.get('locs_no', 'ND'),
            request.form.get('locs_nc', 'ND'),
            request.form.get('locs_c', 'ND'),
            request.form.get('locs_p', 'ND'),
            request.form.get('iol_type', 'ND'),
            request.form.get('aphakia_etiology', 'ND'),
            request.form.get('glaucoma', '0'),
            request.form.get('oht_or_pac', '0'),
            request.form.get('glaucoma_etiology', 'ND'),
            request.form.get('steroid_responder', '0'),
            request.form.get('pxs', '0'),
            request.form.get('pds', '0'),
            request.form.get('diabetic_retinopathy', '0'),
            request.form.get('dr_stage', 'ND'),
            request.form.get('npdr_stage', 'ND'),
            request.form.get('pdr_stage', 'ND'),
            request.form.get('macular_edema', '0'),
            request.form.get('me_etiology', 'ND'),
            request.form.get('macular_degeneration', '0'),
            request.form.get('md_etiology', 'ND'),
            request.form.get('amd_stage', 'ND'),
            request.form.get('amd_exudation', '0'),
            request.form.get('other_md_stage', 'ND'),
            request.form.get('other_md_exudation', '0'),
            request.form.get('mh_vmt', '0'),
            request.form.get('mh_vmt_etiology', 'ND'),
            request.form.get('secondary_mh_vmt_cause', 'ND'),
            request.form.get('mh_vmt_treatment_status', 'ND'),
            request.form.get('epiretinal_membrane', '0'),
            request.form.get('erm_etiology', 'ND'),
            request.form.get('secondary_erm_cause', 'ND'),
            request.form.get('erm_treatment_status', 'ND'),
            request.form.get('retinal_detachment', '0'),
            request.form.get('rd_etiology', 'ND'),
            request.form.get('rd_treatment_status', 'ND'),
            request.form.get('pvr', '0'),
            request.form.get('vitreous_opacification', '0'),
            request.form.get('vh_etiology', 'ND')
        ))

        # Insert other ocular conditions (multiple)
        other_conditions = request.form.getlist('other_ocular_condition[]')
        other_condition_eyes = request.form.getlist('other_ocular_condition_eye[]')
        for i, condition in enumerate(other_conditions):
            if condition and condition not in ['0', '']:
                cur.execute("""
                    INSERT INTO other_ocular_conditions (patient_id, icd10_code, eye)
                    VALUES (%s, %s, %s)
                """, (patient_id, condition, other_condition_eyes[i] if i < len(other_condition_eyes) else 'ND'))

        # Insert previous surgeries (multiple)
        surgeries = request.form.getlist('previous_surgery[]')
        surgery_eyes = request.form.getlist('previous_surgery_eye[]')
        for i, surgery in enumerate(surgeries):
            if surgery and surgery not in ['0', '']:
                cur.execute("""
                    INSERT INTO previous_ocular_surgeries (patient_id, surgery_code, eye)
                    VALUES (%s, %s, %s)
                """, (patient_id, surgery, surgery_eyes[i] if i < len(surgery_eyes) else 'ND'))

        # Insert systemic conditions (multiple)
        systemic_conditions = request.form.getlist('systemic_condition[]')
        for condition in systemic_conditions:
            if condition and condition not in ['0', '']:
                cur.execute("""
                    INSERT INTO systemic_conditions (patient_id, icd10_code)
                    VALUES (%s, %s)
                """, (patient_id, condition))

        # Insert ocular medications (multiple)
        ocular_meds = request.form.getlist('ocular_medication[]')
        ocular_med_eyes = request.form.getlist('ocular_medication_eye[]')
        ocular_med_days = request.form.getlist('ocular_medication_days[]')
        for i, med in enumerate(ocular_meds):
            if med and med not in ['0', '']:
                days = ocular_med_days[i] if i < len(ocular_med_days) and ocular_med_days[i] else None
                cur.execute("""
                    INSERT INTO ocular_medications 
                    (patient_id, trade_name, generic_name, eye, days_before_collection)
                    VALUES (%s, %s, %s, %s, %s)
                """, (patient_id, med, med, ocular_med_eyes[i] if i < len(ocular_med_eyes) else 'ND', days))

        # Insert systemic medications (multiple)
        systemic_meds = request.form.getlist('systemic_medication[]')
        systemic_med_days = request.form.getlist('systemic_medication_days[]')
        for i, med in enumerate(systemic_meds):
            if med and med not in ['0', '']:
                days = systemic_med_days[i] if i < len(systemic_med_days) and systemic_med_days[i] else None
                cur.execute("""
                    INSERT INTO systemic_medications 
                    (patient_id, trade_name, generic_name, days_before_collection)
                    VALUES (%s, %s, %s, %s)
                """, (patient_id, med, med, days))

        conn.commit()
        cur.close()
        conn.close()

        flash(f'Patient #{patient_id} ({patient_name}) successfully created!', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error saving patient: {e}")
        flash(f'Error saving patient: {str(e)}', 'error')
        return redirect(url_for('new_patient'))


@app.route('/validate-data', methods=['GET'])
def validate_data():
    """Search for patients to validate/edit"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['Administrator', 'Staff']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get search parameters
    search_query = request.args.get('q', '')
    search_type = request.args.get('type', 'id')

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('validate_data.html', patients=[])

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        patients = []

        if search_query:
            if search_type == 'id':
                cur.execute("""
                    SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, 
                           ps.date_of_sample_collection, pst.sex, pst.eye
                    FROM patients_sensitive ps
                    JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                    WHERE ps.patient_id::text LIKE %s
                    ORDER BY ps.patient_id
                    LIMIT 50
                """, (f'%{search_query}%',))
            elif search_type == 'name':
                cur.execute("""
                    SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, 
                           ps.date_of_sample_collection, pst.sex, pst.eye
                    FROM patients_sensitive ps
                    JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                    WHERE LOWER(ps.patient_name) LIKE LOWER(%s)
                    ORDER BY ps.patient_name
                    LIMIT 50
                """, (f'%{search_query}%',))
            elif search_type == 'mbo':
                cur.execute("""
                    SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, 
                           ps.date_of_sample_collection, pst.sex, pst.eye
                    FROM patients_sensitive ps
                    JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                    WHERE ps.mbo LIKE %s
                    ORDER BY ps.patient_id
                    LIMIT 50
                """, (f'%{search_query}%',))

            patients = cur.fetchall()
        else:
            # Show recent patients if no search
            cur.execute("""
                SELECT ps.patient_id, ps.patient_name, ps.date_of_birth, 
                       ps.date_of_sample_collection, pst.sex, pst.eye
                FROM patients_sensitive ps
                JOIN patients_statistical pst ON ps.patient_id = pst.patient_id
                ORDER BY ps.created_at DESC
                LIMIT 20
            """)
            patients = cur.fetchall()

        cur.close()
        conn.close()

        return render_template('validate_data.html',
                               patients=patients,
                               search_query=search_query,
                               search_type=search_type)

    except psycopg2.Error as e:
        print(f"Error searching patients: {e}")
        flash('Error searching patients', 'error')
        return render_template('validate_data.html', patients=[])
    finally:
        if conn:
            conn.close()


@app.route('/edit-patient/<int:patient_id>', methods=['GET', 'POST'])
def edit_patient(patient_id):
    """Edit existing patient data"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['Administrator', 'Staff']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('validate_data'))

    if request.method == 'GET':
        # Load patient data
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get sensitive data
            cur.execute("""
                SELECT * FROM patients_sensitive WHERE patient_id = %s
            """, (patient_id,))
            patient = cur.fetchone()

            if not patient:
                flash('Patient not found', 'error')
                return redirect(url_for('validate_data'))

            # Get statistical data
            cur.execute("""
                SELECT * FROM patients_statistical WHERE patient_id = %s
            """, (patient_id,))
            stats = cur.fetchone()

            # Get ocular conditions
            cur.execute("""
                SELECT * FROM ocular_conditions WHERE patient_id = %s
            """, (patient_id,))
            conditions = cur.fetchone()

            # Get other ocular conditions
            cur.execute("""
                SELECT * FROM other_ocular_conditions WHERE patient_id = %s
                ORDER BY id
            """, (patient_id,))
            other_conditions = cur.fetchall()

            # Get previous surgeries
            cur.execute("""
                SELECT * FROM previous_ocular_surgeries WHERE patient_id = %s
                ORDER BY id
            """, (patient_id,))
            surgeries = cur.fetchall()

            # Get systemic conditions
            cur.execute("""
                SELECT * FROM systemic_conditions WHERE patient_id = %s
                ORDER BY id
            """, (patient_id,))
            systemic = cur.fetchall()

            # Get ocular medications
            cur.execute("""
                SELECT * FROM ocular_medications WHERE patient_id = %s
                ORDER BY id
            """, (patient_id,))
            ocular_meds = cur.fetchall()

            # Get systemic medications
            cur.execute("""
                SELECT * FROM systemic_medications WHERE patient_id = %s
                ORDER BY id
            """, (patient_id,))
            systemic_meds = cur.fetchall()

            cur.close()
            conn.close()

            return render_template('edit_patient.html',
                                   patient=patient,
                                   stats=stats,
                                   conditions=conditions,
                                   other_conditions=other_conditions,
                                   surgeries=surgeries,
                                   systemic=systemic,
                                   ocular_meds=ocular_meds,
                                   systemic_meds=systemic_meds)

        except psycopg2.Error as e:
            print(f"Error loading patient: {e}")
            flash('Error loading patient data', 'error')
            return redirect(url_for('validate_data'))

    # Handle POST - update patient
    try:
        cur = conn.cursor()

        # Extract form data (same as new patient)
        patient_name = request.form.get('patient_name')
        mbo = request.form.get('mbo')
        sex = request.form.get('sex')
        eye = request.form.get('eye')

        # Build dates
        dob_day = int(request.form.get('dob_day'))
        dob_month = int(request.form.get('dob_month'))
        dob_year = int(request.form.get('dob_year'))
        date_of_birth = date(dob_year, dob_month, dob_day)

        col_day = int(request.form.get('collection_day'))
        col_month = int(request.form.get('collection_month'))
        col_year = int(request.form.get('collection_year'))
        date_of_collection = date(col_year, col_month, col_day)

        # Update patients_sensitive
        cur.execute("""
            UPDATE patients_sensitive 
            SET patient_name = %s, mbo = %s, date_of_birth = %s, date_of_sample_collection = %s
            WHERE patient_id = %s
        """, (patient_name, mbo, date_of_birth, date_of_collection, patient_id))

        # Update patients_statistical
        person_hash = generate_person_hash(mbo)
        age = calculate_age(date_of_birth, date_of_collection)

        cur.execute("""
            UPDATE patients_statistical 
            SET person_hash = %s, age = %s, sex = %s, eye = %s
            WHERE patient_id = %s
        """, (person_hash, age, sex, eye, patient_id))

        # Update ocular conditions
        cur.execute("""
            UPDATE ocular_conditions SET
                lens_status = %s, locs_iii_no = %s, locs_iii_nc = %s, locs_iii_c = %s, locs_iii_p = %s,
                iol_type = %s, aphakia_etiology = %s, glaucoma = %s, oht_or_pac = %s, glaucoma_etiology = %s,
                steroid_responder = %s, pxs = %s, pds = %s, diabetic_retinopathy = %s, dr_stage = %s,
                npdr_stage = %s, pdr_stage = %s, macular_edema = %s, me_etiology = %s, 
                macular_degeneration = %s, md_etiology = %s, amd_stage = %s, amd_exudation = %s,
                other_md_stage = %s, other_md_exudation = %s, mh_vmt = %s, mh_vmt_etiology = %s,
                secondary_mh_vmt_cause = %s, mh_vmt_treatment_status = %s, epiretinal_membrane = %s,
                erm_etiology = %s, secondary_erm_cause = %s, erm_treatment_status = %s,
                retinal_detachment = %s, rd_etiology = %s, rd_treatment_status = %s, pvr = %s,
                vitreous_opacification = %s, vh_etiology = %s
            WHERE patient_id = %s
        """, (
            request.form.get('lens_status', 'ND'),
            request.form.get('locs_no', 'ND'),
            request.form.get('locs_nc', 'ND'),
            request.form.get('locs_c', 'ND'),
            request.form.get('locs_p', 'ND'),
            request.form.get('iol_type', 'ND'),
            request.form.get('aphakia_etiology', 'ND'),
            request.form.get('glaucoma', '0'),
            request.form.get('oht_or_pac', '0'),
            request.form.get('glaucoma_etiology', 'ND'),
            request.form.get('steroid_responder', '0'),
            request.form.get('pxs', '0'),
            request.form.get('pds', '0'),
            request.form.get('diabetic_retinopathy', '0'),
            request.form.get('dr_stage', 'ND'),
            request.form.get('npdr_stage', 'ND'),
            request.form.get('pdr_stage', 'ND'),
            request.form.get('macular_edema', '0'),
            request.form.get('me_etiology', 'ND'),
            request.form.get('macular_degeneration', '0'),
            request.form.get('md_etiology', 'ND'),
            request.form.get('amd_stage', 'ND'),
            request.form.get('amd_exudation', '0'),
            request.form.get('other_md_stage', 'ND'),
            request.form.get('other_md_exudation', '0'),
            request.form.get('mh_vmt', '0'),
            request.form.get('mh_vmt_etiology', 'ND'),
            request.form.get('secondary_mh_vmt_cause', 'ND'),
            request.form.get('mh_vmt_treatment_status', 'ND'),
            request.form.get('epiretinal_membrane', '0'),
            request.form.get('erm_etiology', 'ND'),
            request.form.get('secondary_erm_cause', 'ND'),
            request.form.get('erm_treatment_status', 'ND'),
            request.form.get('retinal_detachment', '0'),
            request.form.get('rd_etiology', 'ND'),
            request.form.get('rd_treatment_status', 'ND'),
            request.form.get('pvr', '0'),
            request.form.get('vitreous_opacification', '0'),
            request.form.get('vh_etiology', 'ND'),
            patient_id
        ))

        # Delete and re-insert repeatable items
        cur.execute("DELETE FROM other_ocular_conditions WHERE patient_id = %s", (patient_id,))
        cur.execute("DELETE FROM previous_ocular_surgeries WHERE patient_id = %s", (patient_id,))
        cur.execute("DELETE FROM systemic_conditions WHERE patient_id = %s", (patient_id,))
        cur.execute("DELETE FROM ocular_medications WHERE patient_id = %s", (patient_id,))
        cur.execute("DELETE FROM systemic_medications WHERE patient_id = %s", (patient_id,))

        # Re-insert other ocular conditions
        other_conditions = request.form.getlist('other_ocular_condition[]')
        other_condition_eyes = request.form.getlist('other_ocular_condition_eye[]')
        for i, condition in enumerate(other_conditions):
            if condition and condition not in ['0', '']:
                cur.execute("""
                    INSERT INTO other_ocular_conditions (patient_id, icd10_code, eye)
                    VALUES (%s, %s, %s)
                """, (patient_id, condition, other_condition_eyes[i] if i < len(other_condition_eyes) else 'ND'))

        # Re-insert previous surgeries
        surgeries = request.form.getlist('previous_surgery[]')
        surgery_eyes = request.form.getlist('previous_surgery_eye[]')
        for i, surgery in enumerate(surgeries):
            if surgery and surgery not in ['0', '']:
                cur.execute("""
                    INSERT INTO previous_ocular_surgeries (patient_id, surgery_code, eye)
                    VALUES (%s, %s, %s)
                """, (patient_id, surgery, surgery_eyes[i] if i < len(surgery_eyes) else 'ND'))

        # Re-insert systemic conditions
        systemic_conditions = request.form.getlist('systemic_condition[]')
        for condition in systemic_conditions:
            if condition and condition not in ['0', '']:
                cur.execute("""
                    INSERT INTO systemic_conditions (patient_id, icd10_code)
                    VALUES (%s, %s)
                """, (patient_id, condition))

        # Re-insert ocular medications
        ocular_meds = request.form.getlist('ocular_medication[]')
        ocular_med_eyes = request.form.getlist('ocular_medication_eye[]')
        ocular_med_days = request.form.getlist('ocular_medication_days[]')
        for i, med in enumerate(ocular_meds):
            if med and med not in ['0', '']:
                days = ocular_med_days[i] if i < len(ocular_med_days) and ocular_med_days[i] else None
                cur.execute("""
                    INSERT INTO ocular_medications 
                    (patient_id, trade_name, generic_name, eye, days_before_collection)
                    VALUES (%s, %s, %s, %s, %s)
                """, (patient_id, med, med, ocular_med_eyes[i] if i < len(ocular_med_eyes) else 'ND', days))

        # Re-insert systemic medications
        systemic_meds = request.form.getlist('systemic_medication[]')
        systemic_med_days = request.form.getlist('systemic_medication_days[]')
        for i, med in enumerate(systemic_meds):
            if med and med not in ['0', '']:
                days = systemic_med_days[i] if i < len(systemic_med_days) and systemic_med_days[i] else None
                cur.execute("""
                    INSERT INTO systemic_medications 
                    (patient_id, trade_name, generic_name, days_before_collection)
                    VALUES (%s, %s, %s, %s)
                """, (patient_id, med, med, days))

        conn.commit()
        cur.close()
        conn.close()

        flash(f'Patient #{patient_id} ({patient_name}) successfully updated!', 'success')
        return redirect(url_for('validate_data'))

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error updating patient: {e}")
        flash(f'Error updating patient: {str(e)}', 'error')
        return redirect(url_for('edit_patient', patient_id=patient_id))


if __name__ == '__main__':
    print("Checking database...")
    if create_database_if_not_exists():
        print("Initializing database tables...")
        init_database()
    else:
        print("Warning: Could not create/access database.")

    app.run(host='0.0.0.0', port=5000, debug=True)
