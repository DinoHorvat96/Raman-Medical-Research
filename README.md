# Medical Research Database Application

A secure, role-based medical database web application built with Flask and PostgreSQL.

## Features

- 🔐 Secure authentication with bcrypt password hashing
- 👥 Role-based access control (Administrator, Osoblje, Pacijent)
- 🏥 Patient management system
- 📋 Diagnosis tracking with therapy and comments
- 🐳 Docker-ready with nginx reverse proxy
- 🔄 Automatic database initialization with default admin user

## Database Structure

### Tables

1. **korisnici** (Users)
   - `id_korisnika` - Primary key (auto-increment)
   - `korisnicko_ime` - Username (unique)
   - `lozinka` - Hashed password
   - `email` - Email address
   - `rola` - Role: "Pacijent", "Osoblje", or "Administrator"
   - `kreiran` - Creation timestamp
   - `zadnji_login` - Last login timestamp

2. **pacijenti** (Patients)
   - `id_pacijenta` - Primary key (auto-increment)
   - `ime` - First name
   - `prezime` - Last name
   - `datum_rodenja` - Date of birth

3. **dijagnoze** (Diagnoses)
   - `id_dijagnoze` - Primary key (auto-increment)
   - `id_pacijenta` - Foreign key to pacijenti
   - `ime_dijagnoze` - Diagnosis name
   - `terapija` - Therapy (optional text)
   - `komentari` - Doctor's comments (optional)
   - `datum_dijagnoze` - Diagnosis timestamp

## Project Structure

```
medical-research/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Multi-container setup
├── nginx.conf           # Nginx configuration
├── .env                 # Environment variables (create from .env.example)
├── .gitignore          # Git ignore file
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── login.html      # Login page
│   ├── dashboard.html  # Dashboard
│   ├── pacijenti.html  # Patients list
│   └── patient_detail.html  # Patient details
└── README.md           # This file
```

## Quick Start

### Option 1: Docker Compose (Recommended)

1. **Clone or create the project structure** as shown above

2. **Create the .env file** (optional, uses defaults if not provided):
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. **Start all services**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Web application: http://localhost
   - Direct Flask access: http://localhost:5000
   - PostgreSQL: localhost:5432

5. **Default login credentials**:
   - Username: `Admin`
   - Password: `admin123`

### Option 2: Local Development

1. **Install PostgreSQL** (if not already installed)

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database** (create .env file):
   ```
   DB_NAME=istrazivanje_medicina
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_HOST=localhost
   DB_PORT=5432
   SECRET_KEY=your-random-secret-key
   ```

5. **Create the database**:
   ```bash
   createdb istrazivanje_medicina
   # Or via psql:
   psql -U postgres -c "CREATE DATABASE istrazivanje_medicina;"
   ```

6. **Run the application**:
   ```bash
   python app.py
   ```

7. **Access**: http://localhost:5000

## Docker Commands

### View logs
```bash
docker-compose logs -f web      # Flask app logs
docker-compose logs -f postgres # Database logs
docker-compose logs -f nginx    # Nginx logs
```

### Restart services
```bash
docker-compose restart
```

### Stop services
```bash
docker-compose down
```

### Stop and remove volumes (WARNING: deletes all data)
```bash
docker-compose down -v
```

### Access PostgreSQL shell
```bash
docker exec -it medical_postgres psql -U postgres -d istrazivanje_medicina
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

## Database Management

### Manual SQL Access

Connect to the database:
```bash
# Via Docker
docker exec -it medical_postgres psql -U postgres -d istrazivanje_medicina

# Local PostgreSQL
psql -U postgres -d istrazivanje_medicina
```

### Add Sample Data

```sql
-- Add a patient
INSERT INTO pacijenti (ime, prezime, datum_rodenja) 
VALUES ('Marko', 'Marković', '1980-05-15');

-- Add a diagnosis for patient ID 1
INSERT INTO dijagnoze (id_pacijenta, ime_dijagnoze, terapija, komentari)
VALUES (1, 'Hipertenzija', 'Lisinopril 10mg dnevno', 'Preporučena izmjena životnog stila');

-- Add a new user (password: test123)
INSERT INTO korisnici (korisnicko_ime, lozinka, email, rola)
VALUES ('doktor1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5zyorU9F/5C/O', 'doktor@example.com', 'Osoblje');
```

### View Data

```sql
-- View all users
SELECT id_korisnika, korisnicko_ime, email, rola, kreiran, zadnji_login FROM korisnici;

-- View all patients with diagnosis count
SELECT p.*, COUNT(d.id_dijagnoze) as broj_dijagnoza
FROM pacijenti p
LEFT JOIN dijagnoze d ON p.id_pacijenta = d.id_pacijenta
GROUP BY p.id_pacijenta;

-- View patient with their diagnoses
SELECT p.ime, p.prezime, d.ime_dijagnoze, d.terapija, d.datum_dijagnoze
FROM pacijenti p
LEFT JOIN dijagnoze d ON p.id_pacijenta = d.id_pacijenta
WHERE p.id_pacijenta = 1;
```

## User Roles & Access

### Administrator
- Full access to all features
- Can view all statistics
- Can manage all patients and diagnoses
- Future: User management capabilities

### Osoblje (Staff)
- Can view and manage patients
- Can view and add diagnoses
- Access to patient statistics

### Pacijent (Patient)
- Limited access (currently in development)
- Future: View own medical records only

## Security Considerations

### Current Implementation
✅ Password hashing with bcrypt  
✅ Session-based authentication  
✅ Role-based access control  
✅ SQL injection prevention (parameterized queries)  
✅ Basic security headers in nginx  

### Recommended for Production
⚠️ Use HTTPS/SSL certificates  
⚠️ Implement CSRF protection  
⚠️ Add rate limiting  
⚠️ Enable audit logging  
⚠️ Implement data encryption at rest  
⚠️ Use secrets management (e.g., Docker secrets)  
⚠️ Add session timeout  
⚠️ Implement password complexity requirements  
⚠️ Add two-factor authentication  
⚠️ Regular security audits  
⚠️ GDPR/HIPAA compliance measures  

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DB_NAME | istrazivanje_medicina | Database name |
| DB_USER | postgres | Database user |
| DB_PASSWORD | postgres | Database password |
| DB_HOST | localhost | Database host |
| DB_PORT | 5432 | Database port |
| SECRET_KEY | (random) | Flask secret key for sessions |

## Troubleshooting

### Database connection error
- Ensure PostgreSQL is running
- Check database credentials in .env
- Verify network connectivity (for Docker: ensure containers are on same network)

### Port already in use
```bash
# Change ports in docker-compose.yml
ports:
  - "8080:80"    # Change from 80 to 8080
  - "5001:5000"  # Change from 5000 to 5001
```

### Templates not found
- Ensure all HTML files are in `templates/` directory
- Check file names match exactly (case-sensitive)

### Permission denied errors
```bash
# Fix Docker permissions
sudo chown -R $USER:$USER .
```

## Future Enhancements

- [ ] Patient registration and self-service portal
- [ ] Advanced search and filtering
- [ ] Medical report generation (PDF)
- [ ] Appointment scheduling system
- [ ] Medication tracking
- [ ] Lab results integration
- [ ] Multi-language support
- [ ] Mobile-responsive design improvements
- [ ] Data export functionality (CSV, Excel)
- [ ] Audit trail for all actions
- [ ] Email notifications
- [ ] User management interface for admins
- [ ] Advanced analytics and reporting
- [ ] Integration with medical devices/APIs

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Docker/PostgreSQL logs
3. Ensure all dependencies are installed correctly

## License

This is a private medical research project. Ensure compliance with all relevant healthcare data regulations (HIPAA, GDPR, etc.) before deployment.