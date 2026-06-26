import os, re, sqlite3, hashlib, secrets, math
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
DB = "healthcare.db"

# ── helpers ──
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db: db.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*a, **kw):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Access denied.", "danger")
                return redirect(url_for("index"))
            return f(*a, **kw)
        return wrapped
    return decorator

def validate_email(e):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', e)

def validate_phone(p):
    return re.match(r'^\d{10}$', p)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ── init db ──
def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('doctor','patient')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS doctor_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE REFERENCES users(id),
        specialization TEXT NOT NULL,
        experience INTEGER DEFAULT 0,
        fee REAL DEFAULT 500,
        bio TEXT DEFAULT '',
        available INTEGER DEFAULT 1,
        hospital TEXT DEFAULT 'EHealth Clinic',
        address TEXT DEFAULT '',
        latitude REAL DEFAULT 0.0,
        longitude REAL DEFAULT 0.0
    );
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER REFERENCES users(id),
        doctor_id INTEGER REFERENCES users(id),
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        reason TEXT DEFAULT '',
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','completed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        duration_days INTEGER NOT NULL,
        features TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS user_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        subscription_id INTEGER REFERENCES subscriptions(id),
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER REFERENCES users(id),
        receiver_id INTEGER REFERENCES users(id),
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0
    );
    """)
    cur = db.execute("SELECT COUNT(*) FROM subscriptions")
    if cur.fetchone()[0] == 0:
        db.executemany("INSERT INTO subscriptions (name,description,price,duration_days,features) VALUES (?,?,?,?,?)", [
            ("Basic", "Essential health checkups and teleconsultation", 299, 30,
             "2 Consultations/month|Basic health reports|Email support"),
            ("Premium", "Unlimited consultations with priority booking", 799, 30,
             "Unlimited Consultations|Priority booking|24/7 chat support|Health reports"),
            ("Family", "Cover your whole family with comprehensive care", 1499, 30,
             "Up to 5 family members|Unlimited Consultations|Priority booking|24/7 support|Specialist access"),
        ])
    cur = db.execute("SELECT COUNT(*) FROM users WHERE role='doctor'")
    if cur.fetchone()[0] == 0:
        pw = hash_pw("doctor123")
        nims_doctors = [
            {"name":"Dr. Rajesh Kumar",  "email":"rajesh@nims.in", "phone":"9810001001",
             "spec":"Cardiology",       "exp":15,"fee":800,
             "bio":"Senior Cardiologist at NIMS with 15 years experience in interventional cardiology.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4744,"lng":77.5040},
            {"name":"Dr. Priya Sharma",  "email":"priya@nims.in",  "phone":"9810001002",
             "spec":"Gynaecology",      "exp":12,"fee":700,
             "bio":"Expert gynaecologist specializing in high-risk pregnancies and laparoscopic surgery.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4746,"lng":77.5042},
            {"name":"Dr. Anil Verma",    "email":"anil@nims.in",   "phone":"9810001003",
             "spec":"Orthopaedics",     "exp":18,"fee":900,
             "bio":"Chief Orthopaedic Surgeon at NIMS. Specialist in joint replacement and spine surgery.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4742,"lng":77.5038},
            {"name":"Dr. Sunita Rao",    "email":"sunita@nims.in", "phone":"9810001004",
             "spec":"Paediatrics",      "exp":10,"fee":600,
             "bio":"Paediatrician with expertise in neonatal care and childhood immunization programs.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4748,"lng":77.5044},
            {"name":"Dr. Mohit Gupta",   "email":"mohit@nims.in",  "phone":"9810001005",
             "spec":"Neurology",        "exp":14,"fee":1000,
             "bio":"Neurologist specializing in stroke management, epilepsy and movement disorders.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4740,"lng":77.5036},
            {"name":"Dr. Kavita Singh",  "email":"kavita@nims.in", "phone":"9810001006",
             "spec":"Dermatology",      "exp":8, "fee":600,
             "bio":"Dermatologist with expertise in cosmetic dermatology, acne treatment and skin disorders.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4750,"lng":77.5046},
            {"name":"Dr. Deepak Mishra", "email":"deepak@nims.in", "phone":"9810001007",
             "spec":"General Surgery",  "exp":20,"fee":1000,
             "bio":"Senior General Surgeon at NIMS. Expert in laparoscopic and emergency surgeries.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4743,"lng":77.5041},
            {"name":"Dr. Rekha Jain",    "email":"rekha@nims.in",  "phone":"9810001008",
             "spec":"Ophthalmology",    "exp":11,"fee":650,
             "bio":"Eye specialist with expertise in cataract surgery, LASIK and retinal disorders.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4745,"lng":77.5039},
            {"name":"Dr. Sanjay Tyagi",  "email":"sanjay@nims.in", "phone":"9810001009",
             "spec":"ENT",              "exp":9, "fee":550,
             "bio":"ENT specialist handling sinusitis, hearing disorders and throat infections.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4747,"lng":77.5043},
            {"name":"Dr. Nisha Agarwal", "email":"nisha@nims.in",  "phone":"9810001010",
             "spec":"Psychiatry",       "exp":13,"fee":750,
             "bio":"Psychiatrist specializing in anxiety, depression and cognitive behavioural therapy.",
             "hospital":"NIMS Greater Noida","address":"NIMS Hospital, Sector Alpha-1, Greater Noida, UP 201310",
             "lat":28.4741,"lng":77.5037},
        ]
        for d in nims_doctors:
            db.execute("INSERT INTO users (name,email,phone,password,role) VALUES (?,?,?,?,?)",
                       (d["name"],d["email"],d["phone"],pw,"doctor"))
            uid = db.execute("SELECT id FROM users WHERE email=?", (d["email"],)).fetchone()[0]
            db.execute("""INSERT INTO doctor_profiles
                          (user_id,specialization,experience,fee,bio,hospital,address,latitude,longitude)
                          VALUES (?,?,?,?,?,?,?,?,?)""",
                       (uid,d["spec"],d["exp"],d["fee"],d["bio"],
                        d["hospital"],d["address"],d["lat"],d["lng"]))
    db.commit()
    db.close()

# ── routes ──
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name     = request.form.get("name","").strip()
        email    = request.form.get("email","").strip()
        phone    = request.form.get("phone","").strip()
        password = request.form.get("password","")
        confirm  = request.form.get("confirm_password","")
        role     = request.form.get("role","patient")

        errors = []
        if not name or len(name) < 2: errors.append("Name must be at least 2 characters.")
        if not validate_email(email):  errors.append("Enter a valid email address.")
        if not validate_phone(phone):  errors.append("Phone must be exactly 10 digits.")
        if len(password) < 6:          errors.append("Password must be at least 6 characters.")
        if password != confirm:        errors.append("Passwords do not match.")

        if errors:
            for e in errors: flash(e,"danger")
            return render_template("register.html")

        db = get_db()
        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            flash("Email already registered.","danger")
            return render_template("register.html")

        db.execute("INSERT INTO users (name,email,phone,password,role) VALUES (?,?,?,?,?)",
                   (name,email,phone,hash_pw(password),role))
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        if role == "doctor":
            spec = request.form.get("specialization","General")
            exp  = request.form.get("experience","0")
            fee  = request.form.get("fee","500")
            bio  = request.form.get("bio","")
            try: exp = int(exp)
            except: exp = 0
            try: fee = float(fee)
            except: fee = 500
            db.execute("INSERT INTO doctor_profiles (user_id,specialization,experience,fee,bio) VALUES (?,?,?,?,?)",
                       (user_id,spec,exp,fee,bio))
        db.commit()
        flash("Registration successful! Please log in.","success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email","").strip()
        password = request.form.get("password","")
        if not validate_email(email):
            flash("Enter a valid email.","danger")
            return render_template("login.html")
        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE email=? AND password=?",
                          (email,hash_pw(password))).fetchone()
        if not user:
            flash("Invalid email or password.","danger")
            return render_template("login.html")
        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        session["role"]      = user["role"]
        flash(f"Welcome back, {user['name']}!","success")
        return redirect(url_for("doctor_dashboard" if user["role"]=="doctor" else "patient_dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.","info")
    return redirect(url_for("index"))

# ── patient routes ──
@app.route("/patient/dashboard")
@login_required(role="patient")
def patient_dashboard():
    db = get_db()
    appointments = db.execute("""
        SELECT a.*, u.name as doctor_name, dp.specialization
        FROM appointments a
        JOIN users u ON a.doctor_id=u.id
        JOIN doctor_profiles dp ON dp.user_id=u.id
        WHERE a.patient_id=? ORDER BY a.created_at DESC
    """, (session["user_id"],)).fetchall()
    subs = db.execute("""
        SELECT us.*, s.name as plan_name, s.price
        FROM user_subscriptions us
        JOIN subscriptions s ON us.subscription_id=s.id
        WHERE us.user_id=? ORDER BY us.start_date DESC
    """, (session["user_id"],)).fetchall()
    unread = db.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=? AND is_read=0",
                        (session["user_id"],)).fetchone()[0]
    return render_template("patient_dashboard.html", appointments=appointments, subs=subs, unread=unread)

# ── SINGLE browse_doctors route (with location + distance) ──
@app.route("/patient/doctors")
@login_required(role="patient")
def browse_doctors():
    db = get_db()
    rows = db.execute("""
        SELECT u.id, u.name, u.email, dp.*
        FROM users u JOIN doctor_profiles dp ON dp.user_id=u.id
        WHERE u.role='doctor' AND dp.available=1
    """).fetchall()

    try:
        user_lat = float(request.args.get("lat", 0))
        user_lng = float(request.args.get("lng", 0))
        location_granted = (user_lat != 0 or user_lng != 0)
    except (TypeError, ValueError):
        user_lat, user_lng, location_granted = 0.0, 0.0, False

    doctors = []
    for d in rows:
        doc = dict(d)
        if location_granted:
            doc["distance"] = round(haversine(user_lat, user_lng, doc["latitude"], doc["longitude"]), 1)
        else:
            doc["distance"] = None
        doctors.append(doc)

    if location_granted:
        doctors.sort(key=lambda x: x["distance"])

    return render_template("browse_doctors.html",
                           doctors=doctors,
                           location_granted=location_granted)

@app.route("/patient/book/<int:doctor_id>", methods=["GET","POST"])
@login_required(role="patient")
def book_appointment(doctor_id):
    db = get_db()
    doctor = db.execute("""
        SELECT u.id, u.name, dp.* FROM users u
        JOIN doctor_profiles dp ON dp.user_id=u.id WHERE u.id=?
    """, (doctor_id,)).fetchone()
    if not doctor:
        flash("Doctor not found.","danger")
        return redirect(url_for("browse_doctors"))
    if request.method == "POST":
        date   = request.form.get("date","")
        time   = request.form.get("time","")
        reason = request.form.get("reason","").strip()
        if not date or not time:
            flash("Please select date and time.","danger")
            return render_template("book_appointment.html", doctor=doctor)
        db.execute("INSERT INTO appointments (patient_id,doctor_id,date,time,reason) VALUES (?,?,?,?,?)",
                   (session["user_id"],doctor_id,date,time,reason))
        db.commit()
        flash("Appointment booked successfully!","success")
        return redirect(url_for("patient_dashboard"))
    return render_template("book_appointment.html", doctor=doctor)

@app.route("/patient/subscriptions")
@login_required(role="patient")
def view_subscriptions():
    db   = get_db()
    plans = db.execute("SELECT * FROM subscriptions").fetchall()
    return render_template("subscriptions.html", plans=plans)

@app.route("/patient/subscribe/<int:plan_id>", methods=["POST"])
@login_required(role="patient")
def subscribe(plan_id):
    return redirect(url_for("payment_page", plan_id=plan_id))

# ── UPI Payment ──
UPI_ID        = "vansh@upi"
MERCHANT_NAME = "EHealth"

@app.route("/payment/<int:plan_id>")
@login_required(role="patient")
def payment_page(plan_id):
    db   = get_db()
    plan = db.execute("SELECT * FROM subscriptions WHERE id=?", (plan_id,)).fetchone()
    if not plan:
        flash("Plan not found.","danger")
        return redirect(url_for("view_subscriptions"))
    upi_url = (
        f"upi://pay?pa={UPI_ID}"
        f"&pn={MERCHANT_NAME.replace(' ','%20')}"
        f"&am={int(plan['price'])}"
        f"&cu=INR"
        f"&tn={plan['name'].replace(' ','%20')}%20Subscription"
    )
    return render_template("payment.html", plan=plan, upi_id=UPI_ID,
                           merchant=MERCHANT_NAME, upi_url=upi_url)

@app.route("/payment/confirm/<int:plan_id>", methods=["POST"])
@login_required(role="patient")
def confirm_payment(plan_id):
    from datetime import timedelta
    db   = get_db()
    plan = db.execute("SELECT * FROM subscriptions WHERE id=?", (plan_id,)).fetchone()
    if not plan:
        flash("Plan not found.","danger")
        return redirect(url_for("view_subscriptions"))
    start = datetime.now().strftime("%Y-%m-%d")
    end   = (datetime.now() + timedelta(days=plan["duration_days"])).strftime("%Y-%m-%d")
    db.execute("UPDATE user_subscriptions SET active=0 WHERE user_id=? AND active=1", (session["user_id"],))
    db.execute("INSERT INTO user_subscriptions (user_id,subscription_id,start_date,end_date) VALUES (?,?,?,?)",
               (session["user_id"],plan_id,start,end))
    db.commit()
    flash(f"🎉 Successfully subscribed to {plan['name']} plan!","success")
    return redirect(url_for("patient_dashboard"))

# ── doctor routes ──
@app.route("/doctor/dashboard")
@login_required(role="doctor")
def doctor_dashboard():
    db = get_db()
    appointments = db.execute("""
        SELECT a.*, u.name as patient_name, u.phone as patient_phone
        FROM appointments a JOIN users u ON a.patient_id=u.id
        WHERE a.doctor_id=? ORDER BY a.date DESC
    """, (session["user_id"],)).fetchall()
    pending   = sum(1 for a in appointments if a["status"]=="pending")
    approved  = sum(1 for a in appointments if a["status"]=="approved")
    completed = sum(1 for a in appointments if a["status"]=="completed")
    unread    = db.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=? AND is_read=0",
                           (session["user_id"],)).fetchone()[0]
    return render_template("doctor_dashboard.html", appointments=appointments,
                           pending=pending, approved=approved, completed=completed, unread=unread)

@app.route("/doctor/appointment/<int:appt_id>/<action>")
@login_required(role="doctor")
def update_appointment(appt_id, action):
    if action not in ("approved","rejected","completed"):
        flash("Invalid action.","danger")
        return redirect(url_for("doctor_dashboard"))
    db = get_db()
    db.execute("UPDATE appointments SET status=? WHERE id=? AND doctor_id=?",
               (action,appt_id,session["user_id"]))
    db.commit()
    flash(f"Appointment {action}.","success")
    return redirect(url_for("doctor_dashboard"))

@app.route("/doctor/profile", methods=["GET","POST"])
@login_required(role="doctor")
def doctor_profile():
    db = get_db()
    if request.method == "POST":
        spec  = request.form.get("specialization","")
        exp   = request.form.get("experience","0")
        fee   = request.form.get("fee","500")
        bio   = request.form.get("bio","")
        avail = 1 if request.form.get("available") else 0
        try: exp = int(exp)
        except: exp = 0
        try: fee = float(fee)
        except: fee = 500
        db.execute("""UPDATE doctor_profiles
                      SET specialization=?,experience=?,fee=?,bio=?,available=?
                      WHERE user_id=?""", (spec,exp,fee,bio,avail,session["user_id"]))
        db.commit()
        flash("Profile updated.","success")
    profile = db.execute("SELECT * FROM doctor_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
    user    = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return render_template("doctor_profile.html", profile=profile, user=user)

# ── chat ──
@app.route("/chat/<int:other_id>", methods=["GET","POST"])
@login_required()
def chat(other_id):
    db    = get_db()
    other = db.execute("SELECT * FROM users WHERE id=?", (other_id,)).fetchone()
    if not other:
        flash("User not found.","danger")
        return redirect(url_for("index"))
    if request.method == "POST":
        msg = request.form.get("message","").strip()
        if msg:
            db.execute("INSERT INTO messages (sender_id,receiver_id,message) VALUES (?,?,?)",
                       (session["user_id"],other_id,msg))
            db.commit()
    db.execute("UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=?",
               (other_id,session["user_id"]))
    db.commit()
    messages = db.execute("""
        SELECT m.*, u.name as sender_name FROM messages m
        JOIN users u ON m.sender_id=u.id
        WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)
        ORDER BY m.created_at ASC
    """, (session["user_id"],other_id,other_id,session["user_id"])).fetchall()
    return render_template("chat.html", messages=messages, other=other)

@app.route("/chat/contacts")
@login_required()
def chat_contacts():
    db   = get_db()
    uid  = session["user_id"]
    role = session["role"]
    if role == "patient":
        contacts = db.execute("""
            SELECT DISTINCT u.id, u.name, dp.specialization FROM users u
            JOIN doctor_profiles dp ON dp.user_id=u.id
            JOIN appointments a ON (a.doctor_id=u.id AND a.patient_id=?)
            WHERE u.role='doctor'
        """, (uid,)).fetchall()
    else:
        contacts = db.execute("""
            SELECT DISTINCT u.id, u.name FROM users u
            JOIN appointments a ON (a.patient_id=u.id AND a.doctor_id=?)
            WHERE u.role='patient'
        """, (uid,)).fetchall()
    return render_template("chat_contacts.html", contacts=contacts)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)