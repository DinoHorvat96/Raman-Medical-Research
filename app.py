import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
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
DB_NAME = os.getenv('DB_NAME', 'istrazivanje_medicina')
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

        # Connect to PostgreSQL server (postgres database)
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
        print(f"Error code: {e.pgcode}")
        print(f"Error details: {e.pgerror}")
        print("\nPlease create the database manually using:")
        print(f"  psql -h {DB_CONFIG['host']} -p {DB_CONFIG['port']} -U {DB_CONFIG['user']} -d postgres")
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


def init_database():
    """Initialize database with tables and default admin user"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()

        # Create korisnici table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS korisnici (
                id_korisnika SERIAL PRIMARY KEY,
                korisnicko_ime VARCHAR(100) UNIQUE NOT NULL,
                lozinka VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                rola VARCHAR(50) NOT NULL CHECK (rola IN ('Pacijent', 'Osoblje', 'Administrator')),
                kreiran TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                zadnji_login TIMESTAMP
            )
        """)

        # Create pacijenti table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pacijenti (
                id_pacijenta SERIAL PRIMARY KEY,
                ime VARCHAR(100) NOT NULL,
                prezime VARCHAR(100) NOT NULL,
                datum_rodenja DATE NOT NULL
            )
        """)

        # Create dijagnoze table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dijagnoze (
                id_dijagnoze SERIAL PRIMARY KEY,
                id_pacijenta INTEGER NOT NULL REFERENCES pacijenti(id_pacijenta) ON DELETE CASCADE,
                ime_dijagnoze VARCHAR(255) NOT NULL,
                terapija TEXT,
                komentari TEXT,
                datum_dijagnoze TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check if admin user exists
        cur.execute("SELECT id_korisnika FROM korisnici WHERE korisnicko_ime = 'Admin'")
        if not cur.fetchone():
            # Create default admin user
            hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
            cur.execute("""
                INSERT INTO korisnici (korisnicko_ime, lozinka, rola, kreiran)
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


@app.route('/')
def index():
    """Main page - redirect to login if not authenticated"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
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
                SELECT id_korisnika, korisnicko_ime, lozinka, rola, email
                FROM korisnici
                WHERE korisnicko_ime = %s
            """, (username,))

            user = cur.fetchone()

            if user and bcrypt.check_password_hash(user['lozinka'], password):
                # Update last login
                cur.execute("""
                    UPDATE korisnici
                    SET zadnji_login = %s
                    WHERE id_korisnika = %s
                """, (datetime.now(), user['id_korisnika']))
                conn.commit()

                # Set session
                session['user_id'] = user['id_korisnika']
                session['username'] = user['korisnicko_ime']
                session['role'] = user['rola']

                flash(f'Welcome, {user["korisnicko_ime"]}!', 'success')
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
    """Logout user"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    """Dashboard page - role-based content"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_role = session.get('role')
    username = session.get('username')

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('dashboard.html', role=user_role, username=username)

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get statistics based on role
        stats = {}

        if user_role in ['Administrator', 'Osoblje']:
            # Get patient count
            cur.execute("SELECT COUNT(*) as count FROM pacijenti")
            stats['total_patients'] = cur.fetchone()['count']

            # Get diagnosis count
            cur.execute("SELECT COUNT(*) as count FROM dijagnoze")
            stats['total_diagnoses'] = cur.fetchone()['count']

            # Get user count (admin only)
            if user_role == 'Administrator':
                cur.execute("SELECT COUNT(*) as count FROM korisnici")
                stats['total_users'] = cur.fetchone()['count']

        cur.close()
        return render_template('dashboard.html', role=user_role, username=username, stats=stats)

    except psycopg2.Error as e:
        print(f"Dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        return render_template('dashboard.html', role=user_role, username=username)
    finally:
        conn.close()


@app.route('/pacijenti')
def pacijenti():
    """View all patients (Osoblje and Administrator only)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['Administrator', 'Osoblje']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('pacijenti.html', patients=[])

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get all patients with their diagnosis count
        cur.execute("""
            SELECT p.*, COUNT(d.id_dijagnoze) as broj_dijagnoza
            FROM pacijenti p
            LEFT JOIN dijagnoze d ON p.id_pacijenta = d.id_pacijenta
            GROUP BY p.id_pacijenta
            ORDER BY p.prezime, p.ime
        """)

        patients = cur.fetchall()
        cur.close()

        return render_template('pacijenti.html', patients=patients)

    except psycopg2.Error as e:
        print(f"Error loading patients: {e}")
        flash('Error loading patients', 'error')
        return render_template('pacijenti.html', patients=[])
    finally:
        conn.close()


@app.route('/pacijent/<int:patient_id>')
def patient_detail(patient_id):
    """View patient details with diagnoses"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') not in ['Administrator', 'Osoblje']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('pacijenti'))

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Get patient info
        cur.execute("SELECT * FROM pacijenti WHERE id_pacijenta = %s", (patient_id,))
        patient = cur.fetchone()

        if not patient:
            flash('Patient not found', 'error')
            return redirect(url_for('pacijenti'))

        # Get patient diagnoses
        cur.execute("""
            SELECT * FROM dijagnoze
            WHERE id_pacijenta = %s
            ORDER BY datum_dijagnoze DESC
        """, (patient_id,))

        diagnoses = cur.fetchall()
        cur.close()

        return render_template('patient_detail.html', patient=patient, diagnoses=diagnoses)

    except psycopg2.Error as e:
        print(f"Error loading patient details: {e}")
        flash('Error loading patient details', 'error')
        return redirect(url_for('pacijenti'))
    finally:
        conn.close()


if __name__ == '__main__':
    # Create database if it doesn't exist
    print("Checking database...")
    if create_database_if_not_exists():
        # Initialize database tables on startup
        print("Initializing database tables...")
        init_database()
    else:
        print("Warning: Could not create/access database. Please check your PostgreSQL connection.")

    # Run the application
    app.run(host='0.0.0.0', port=5000, debug=True)
