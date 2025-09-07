from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("events.db")

app = Flask(__name__, static_folder="templates", static_url_path="")
CORS(app)  # allow calls from 127.0.0.1:5500 etc.


# ---------------------------- DB helpers ---------------------------- #
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # dict-like rows
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # colleges kept simple; use college_id as a short string for scale assumption
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            date TEXT NOT NULL,                 -- ISO date
            type TEXT NOT NULL DEFAULT 'General',-- Workshop/Fest/Seminar/Other
            college_id TEXT NOT NULL DEFAULT 'C-001'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            college_id TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            attendance INTEGER NOT NULL DEFAULT 0,   -- 0/1
            feedback INTEGER,                        -- 1..5
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_id, student_id),
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()

init_db()


# simple helper that separates SELECT vs non-SELECT automatically
def execute(sql, params=(), one=False):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    if sql.strip().lower().startswith("select"):
        rows = cur.fetchall()
        conn.close()
        if one:
            return dict(rows[0]) if rows else None
        return [dict(r) for r in rows]
    else:
        conn.commit()
        last_id = cur.lastrowid
        conn.close()
        return last_id


# ---------------------------- routes ---------------------------- #
@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

# Serve the demo UI if you open http://127.0.0.1:5000/
@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


# -------- Events -------- #
@app.route("/api/events", methods=["GET"])
def list_events():
    q_type = request.args.get("type")  # optional filter
    q_college = request.args.get("college_id")
    sql = "SELECT * FROM events WHERE 1=1"
    params = []
    if q_type:
        sql += " AND type = ?"
        params.append(q_type)
    if q_college:
        sql += " AND college_id = ?"
        params.append(q_college)
    sql += " ORDER BY date ASC, id ASC"
    rows = execute(sql, params)
    return jsonify(rows)

@app.route("/api/events", methods=["POST"])
def create_event():
    data = request.get_json(force=True, silent=True) or {}
    title = data.get("title")
    description = data.get("description")
    date = data.get("date")
    etype = data.get("type", "General")
    college_id = data.get("college_id", "C-001")

    if not title or not description or not date:
        return jsonify({"error": "Missing fields: title/description/date"}), 400

    new_id = execute(
        "INSERT INTO events (title, description, date, type, college_id) VALUES (?,?,?,?,?)",
        (title, description, date, etype, college_id)
    )
    created = execute("SELECT * FROM events WHERE id=?", (new_id,), one=True)
    return jsonify(created), 201


# -------- Students -------- #
@app.route("/api/students", methods=["GET"])
def list_students():
    q_college = request.args.get("college_id")
    sql = "SELECT * FROM students"
    params = []
    if q_college:
        sql += " WHERE college_id = ?"
        params.append(q_college)
    sql += " ORDER BY id DESC"
    return jsonify(execute(sql, params))

@app.route("/api/students", methods=["POST"])
def create_student():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    college_id = data.get("college_id")

    if not name or not email or not college_id:
        return jsonify({"error": "Missing fields: name/email/college_id"}), 400

    try:
        new_id = execute(
            "INSERT INTO students (name, email, college_id) VALUES (?,?,?)",
            (name, email, college_id)
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 400

    created = execute("SELECT * FROM students WHERE id=?", (new_id,), one=True)
    return jsonify(created), 201


# -------- Registrations / Attendance / Feedback -------- #
@app.route("/api/registrations", methods=["GET"])
def list_registrations():
    event_id = request.args.get("event_id")
    student_id = request.args.get("student_id")
    sql = """
        SELECT r.*, e.title AS event_title, s.name AS student_name
        FROM registrations r
        JOIN events e   ON e.id = r.event_id
        JOIN students s ON s.id = r.student_id
        WHERE 1=1
    """
    params = []
    if event_id:
        sql += " AND r.event_id = ?"
        params.append(event_id)
    if student_id:
        sql += " AND r.student_id = ?"
        params.append(student_id)
    sql += " ORDER BY r.created_at DESC"
    return jsonify(execute(sql, params))

@app.route("/api/register", methods=["POST"])
def register_student():
    data = request.get_json(force=True, silent=True) or {}
    event_id = data.get("event_id")
    student_id = data.get("student_id")
    if not event_id or not student_id:
        return jsonify({"error": "Missing event_id/student_id"}), 400
    try:
        new_id = execute(
            "INSERT INTO registrations (event_id, student_id) VALUES (?,?)",
            (event_id, student_id)
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "Student is already registered for this event"}), 400

    created = execute("SELECT * FROM registrations WHERE id=?", (new_id,), one=True)
    return jsonify(created), 201

@app.route("/api/attendance", methods=["POST"])
def mark_attendance():
    data = request.get_json(force=True, silent=True) or {}
    reg_id = data.get("registration_id")
    present = int(bool(data.get("present", 1)))  # default present=1
    if not reg_id:
        return jsonify({"error": "Missing registration_id"}), 400
    execute("UPDATE registrations SET attendance=? WHERE id=?", (present, reg_id))
    updated = execute("SELECT * FROM registrations WHERE id=?", (reg_id,), one=True)
    return jsonify(updated)

@app.route("/api/feedback", methods=["POST"])
def give_feedback():
    data = request.get_json(force=True, silent=True) or {}
    reg_id = data.get("registration_id")
    feedback = data.get("feedback")
    if not reg_id or feedback is None:
        return jsonify({"error": "Missing registration_id/feedback"}), 400
    try:
        f = int(feedback)
        if f < 1 or f > 5:
            raise ValueError
    except Exception:
        return jsonify({"error": "Feedback must be an integer 1–5"}), 400

    execute("UPDATE registrations SET feedback=? WHERE id=?", (f, reg_id))
    updated = execute("SELECT * FROM registrations WHERE id=?", (reg_id,), one=True)
    return jsonify(updated)


# -------- Reports -------- #
@app.route("/api/reports/registrations", methods=["GET"])
def report_registrations():
    rows = execute("""
        SELECT e.id, e.title, e.type, e.college_id,
               COUNT(r.id) AS registrations
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id
        GROUP BY e.id
        ORDER BY registrations DESC, e.title ASC
    """)
    return jsonify(rows)

@app.route("/api/reports/attendance", methods=["GET"])
def report_attendance():
    rows = execute("""
        SELECT e.id, e.title,
               COUNT(r.id) AS total,
               COALESCE(SUM(r.attendance),0) AS attended,
               CASE WHEN COUNT(r.id)=0 THEN 0.0
                    ELSE ROUND(SUM(r.attendance)*100.0/COUNT(r.id), 2) END AS attendance_pct
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id
        GROUP BY e.id
        ORDER BY attendance_pct DESC, e.title ASC
    """)
    return jsonify(rows)

@app.route("/api/reports/feedback", methods=["GET"])
def report_feedback():
    rows = execute("""
        SELECT e.id, e.title,
               ROUND(AVG(r.feedback), 2) AS avg_feedback
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id AND r.feedback IS NOT NULL
        GROUP BY e.id
        HAVING COUNT(r.feedback) > 0
        ORDER BY avg_feedback DESC, e.title ASC
    """)
    return jsonify(rows)

# Bonus – most active students
@app.route("/api/reports/top-students", methods=["GET"])
def report_top_students():
    limit = int(request.args.get("limit", 3))
    rows = execute(f"""
        SELECT s.id, s.name, s.email, s.college_id,
               SUM(r.attendance) AS events_attended,
               COUNT(r.id) AS registrations
        FROM students s
        LEFT JOIN registrations r ON r.student_id = s.id
        GROUP BY s.id
        ORDER BY events_attended DESC, registrations DESC, s.name ASC
        LIMIT {limit}
    """)
    return jsonify(rows)


if __name__ == "__main__":
    # run: python app.py
    app.run(debug=True, port=5000)
