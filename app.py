import os
import sqlite3
from datetime import datetime, timedelta, date
from functools import wraps
from uuid import uuid4

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    abort,
    jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "cambia-esta-clave-secreta-por-una-mas-segura"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


# -------------------------
# Database helpers
# -------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS directions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            responsible_name TEXT,
            email TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'direction')),
            direction_id INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (direction_id) REFERENCES directions(id)
        );

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT,
            direction_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            assigned_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            priority TEXT NOT NULL CHECK(priority IN ('Alta', 'Media', 'Baja')),
            status TEXT NOT NULL CHECK(status IN ('Pendiente', 'En proceso', 'Concluida', 'Vencida')),
            progress INTEGER NOT NULL DEFAULT 0,
            observations TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (direction_id) REFERENCES directions(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            progress INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )

    conn.commit()

    direction_count = cur.execute("SELECT COUNT(*) AS total FROM directions").fetchone()["total"]
    if direction_count == 0:
        sample_directions = [
            ("Coordinación de Gabinete", "Administrador General", "gabinete@bahiadebanderas.gob.mx", now_iso()),
            ("Servicios Públicos", "Titular Servicios Públicos", "servicios@bahiadebanderas.gob.mx", now_iso()),
            ("Obras Públicas", "Titular Obras Públicas", "obras@bahiadebanderas.gob.mx", now_iso()),
            ("Seguridad Ciudadana", "Titular Seguridad", "seguridad@bahiadebanderas.gob.mx", now_iso()),
        ]
        cur.executemany(
            "INSERT INTO directions(name, responsible_name, email, created_at) VALUES (?, ?, ?, ?)",
            sample_directions,
        )
        conn.commit()

    user_count = cur.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    if user_count == 0:
        gabinete_id = cur.execute(
            "SELECT id FROM directions WHERE name = ?", ("Coordinación de Gabinete",)
        ).fetchone()["id"]
        servicios_id = cur.execute(
            "SELECT id FROM directions WHERE name = ?", ("Servicios Públicos",)
        ).fetchone()["id"]
        obras_id = cur.execute(
            "SELECT id FROM directions WHERE name = ?", ("Obras Públicas",)
        ).fetchone()["id"]

        users = [
            (
                "Administrador General",
                "admin",
                generate_password_hash("admin123"),
                "admin",
                gabinete_id,
                1,
                now_iso(),
            ),
            (
                "Usuario Servicios Públicos",
                "servicios",
                generate_password_hash("servicios123"),
                "direction",
                servicios_id,
                1,
                now_iso(),
            ),
            (
                "Usuario Obras Públicas",
                "obras",
                generate_password_hash("obras123"),
                "direction",
                obras_id,
                1,
                now_iso(),
            ),
        ]
        cur.executemany(
            """
            INSERT INTO users(full_name, username, password_hash, role, direction_id, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            users,
        )
        conn.commit()

    activity_count = cur.execute("SELECT COUNT(*) AS total FROM activities").fetchone()["total"]
    if activity_count == 0:
        admin_id = cur.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()["id"]
        servicios_id = cur.execute("SELECT id FROM directions WHERE name = ?", ("Servicios Públicos",)).fetchone()["id"]
        obras_id = cur.execute("SELECT id FROM directions WHERE name = ?", ("Obras Públicas",)).fetchone()["id"]
        today = date.today()
        samples = [
            (
                "CG-001",
                "Entrega de informe semanal",
                "Remitir informe semanal de avances operativos y administrativos.",
                servicios_id,
                admin_id,
                today.isoformat(),
                (today + timedelta(days=5)).isoformat(),
                "Alta",
                "En proceso",
                40,
                "Pendiente complementar evidencia fotográfica.",
                now_iso(),
                now_iso(),
            ),
            (
                "CG-002",
                "Revisión de obra prioritaria",
                "Actualizar estatus de obra pública prioritaria del trimestre.",
                obras_id,
                admin_id,
                today.isoformat(),
                (today + timedelta(days=2)).isoformat(),
                "Media",
                "Pendiente",
                0,
                "Esperando primer reporte.",
                now_iso(),
                now_iso(),
            ),
        ]
        cur.executemany(
            """
            INSERT INTO activities(
                folio, title, description, direction_id, created_by, assigned_date, due_date,
                priority, status, progress, observations, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            samples,
        )
        conn.commit()

    conn.close()


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return date.today().isoformat()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------------
# Auth helpers
# -------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute(
        """
        SELECT u.*, d.name AS direction_name
        FROM users u
        LEFT JOIN directions d ON d.id = u.direction_id
        WHERE u.id = ?
        """,
        (session["user_id"],),
    ).fetchone()
    conn.close()
    return user


# -------------------------
# Business helpers
# -------------------------
def status_color(activity):
    remaining = days_remaining(activity["due_date"])
    if activity["status"] == "Concluida":
        return "success"
    if remaining < 0:
        return "danger"
    if remaining <= 3:
        return "warning"
    return "primary"


def days_remaining(due_date_str):
    due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    return (due - date.today()).days


def normalize_activity_status(progress, due_date_str):
    if progress >= 100:
        return "Concluida"
    if days_remaining(due_date_str) < 0:
        return "Vencida"
    if progress > 0:
        return "En proceso"
    return "Pendiente"


def refresh_overdue_statuses():
    conn = get_db()
    rows = conn.execute("SELECT id, progress, due_date FROM activities").fetchall()
    for row in rows:
        status = normalize_activity_status(row["progress"], row["due_date"])
        conn.execute(
            "UPDATE activities SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), row["id"]),
        )
    conn.commit()
    conn.close()


def get_dashboard_counts(direction_id=None):
    conn = get_db()
    params = []
    where = ""
    if direction_id:
        where = "WHERE direction_id = ?"
        params.append(direction_id)

    total = conn.execute(f"SELECT COUNT(*) AS c FROM activities {where}", params).fetchone()["c"]
    pending = conn.execute(
        f"SELECT COUNT(*) AS c FROM activities {where} {'AND' if where else 'WHERE'} status = 'Pendiente'",
        params,
    ).fetchone()["c"]
    in_progress = conn.execute(
        f"SELECT COUNT(*) AS c FROM activities {where} {'AND' if where else 'WHERE'} status = 'En proceso'",
        params,
    ).fetchone()["c"]
    done = conn.execute(
        f"SELECT COUNT(*) AS c FROM activities {where} {'AND' if where else 'WHERE'} status = 'Concluida'",
        params,
    ).fetchone()["c"]
    overdue = conn.execute(
        f"SELECT COUNT(*) AS c FROM activities {where} {'AND' if where else 'WHERE'} status = 'Vencida'",
        params,
    ).fetchone()["c"]
    conn.close()
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "done": done,
        "overdue": overdue,
    }


@app.context_processor
def inject_globals():
    return {
        "session": session,
        "current_year": datetime.now().year,
    }


# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["direction_id"] = user["direction_id"]
            session["full_name"] = user["full_name"]
            flash(f"Bienvenido, {user['full_name']}", "success")
            return redirect(url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión finalizada.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    refresh_overdue_statuses()
    user = current_user()
    conn = get_db()
    if session.get("role") == "admin":
        activities = conn.execute(
            """
            SELECT a.*, d.name AS direction_name
            FROM activities a
            JOIN directions d ON d.id = a.direction_id
            ORDER BY a.due_date ASC, a.id DESC
            LIMIT 12
            """
        ).fetchall()
        directions = conn.execute(
            "SELECT id, name FROM directions ORDER BY name"
        ).fetchall()
        counts = get_dashboard_counts()
        conn.close()
        return render_template(
            "dashboard_admin.html",
            user=user,
            activities=activities,
            directions=directions,
            counts=counts,
            days_remaining=days_remaining,
            status_color=status_color,
        )
    else:
        activities = conn.execute(
            """
            SELECT a.*, d.name AS direction_name
            FROM activities a
            JOIN directions d ON d.id = a.direction_id
            WHERE a.direction_id = ?
            ORDER BY a.due_date ASC, a.id DESC
            """,
            (session.get("direction_id"),),
        ).fetchall()
        counts = get_dashboard_counts(session.get("direction_id"))
        conn.close()
        return render_template(
            "dashboard_direction.html",
            user=user,
            activities=activities,
            counts=counts,
            days_remaining=days_remaining,
            status_color=status_color,
        )


@app.route("/activities/new", methods=["GET", "POST"])
@login_required
@admin_required
def activity_new():
    conn = get_db()
    directions = conn.execute("SELECT id, name FROM directions ORDER BY name").fetchall()
    if request.method == "POST":
        folio = request.form.get("folio", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        direction_id = request.form.get("direction_id")
        assigned_date = request.form.get("assigned_date") or today_str()
        due_date = request.form.get("due_date")
        priority = request.form.get("priority", "Media")
        observations = request.form.get("observations", "").strip()
        progress = int(request.form.get("progress") or 0)

        if not all([folio, title, direction_id, assigned_date, due_date, priority]):
            flash("Todos los campos obligatorios deben llenarse.", "danger")
            return render_template("activity_form.html", directions=directions, activity=None)

        status = normalize_activity_status(progress, due_date)
        try:
            conn.execute(
                """
                INSERT INTO activities(
                    folio, title, description, direction_id, created_by, assigned_date,
                    due_date, priority, status, progress, observations, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folio,
                    title,
                    description,
                    int(direction_id),
                    session["user_id"],
                    assigned_date,
                    due_date,
                    priority,
                    status,
                    progress,
                    observations,
                    now_iso(),
                    now_iso(),
                ),
            )
            conn.commit()
            flash("Actividad creada correctamente.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("El folio ya existe. Usa uno distinto.", "danger")

    conn.close()
    return render_template("activity_form.html", directions=directions, activity=None)


@app.route("/activities/<int:activity_id>", methods=["GET", "POST"])
@login_required
def activity_detail(activity_id):
    refresh_overdue_statuses()
    conn = get_db()
    activity = conn.execute(
        """
        SELECT a.*, d.name AS direction_name
        FROM activities a
        JOIN directions d ON d.id = a.direction_id
        WHERE a.id = ?
        """,
        (activity_id,),
    ).fetchone()

    if not activity:
        conn.close()
        abort(404)

    if session.get("role") != "admin" and activity["direction_id"] != session.get("direction_id"):
        conn.close()
        abort(403)

    if request.method == "POST":
        comment = request.form.get("comment", "").strip()
        progress = int(request.form.get("progress") or activity["progress"])
        uploaded = request.files.get("file")

        if comment:
            conn.execute(
                "INSERT INTO updates(activity_id, user_id, comment, progress, created_at) VALUES (?, ?, ?, ?, ?)",
                (activity_id, session["user_id"], comment, progress, now_iso()),
            )

        if uploaded and uploaded.filename:
            if not allowed_file(uploaded.filename):
                flash("Archivo no permitido.", "danger")
                conn.close()
                return redirect(url_for("activity_detail", activity_id=activity_id))
            ext = uploaded.filename.rsplit(".", 1)[1].lower()
            original_name = secure_filename(uploaded.filename)
            stored_name = f"{uuid4().hex}.{ext}"
            uploaded.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))
            conn.execute(
                "INSERT INTO files(activity_id, user_id, original_name, stored_name, created_at) VALUES (?, ?, ?, ?, ?)",
                (activity_id, session["user_id"], original_name, stored_name, now_iso()),
            )

        status = normalize_activity_status(progress, activity["due_date"])
        conn.execute(
            "UPDATE activities SET progress = ?, status = ?, updated_at = ? WHERE id = ?",
            (progress, status, now_iso(), activity_id),
        )
        conn.commit()
        flash("Actividad actualizada correctamente.", "success")
        conn.close()
        return redirect(url_for("activity_detail", activity_id=activity_id))

    updates = conn.execute(
        """
        SELECT up.*, u.full_name
        FROM updates up
        JOIN users u ON u.id = up.user_id
        WHERE up.activity_id = ?
        ORDER BY up.id DESC
        """,
        (activity_id,),
    ).fetchall()
    files = conn.execute(
        """
        SELECT f.*, u.full_name
        FROM files f
        JOIN users u ON u.id = f.user_id
        WHERE f.activity_id = ?
        ORDER BY f.id DESC
        """,
        (activity_id,),
    ).fetchall()
    conn.close()

    return render_template(
        "activity_detail.html",
        activity=activity,
        updates=updates,
        files=files,
        days_remaining=days_remaining,
        status_color=status_color,
    )


@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    conn = get_db()
    directions = conn.execute("SELECT id, name FROM directions ORDER BY name").fetchall()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "direction")
        direction_id = request.form.get("direction_id") or None

        if not all([full_name, username, password, role]):
            flash("Completa los campos obligatorios del usuario.", "danger")
        else:
            try:
                conn.execute(
                    """
                    INSERT INTO users(full_name, username, password_hash, role, direction_id, active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        full_name,
                        username,
                        generate_password_hash(password),
                        role,
                        int(direction_id) if direction_id else None,
                        now_iso(),
                    ),
                )
                conn.commit()
                flash("Usuario creado correctamente.", "success")
                return redirect(url_for("users"))
            except sqlite3.IntegrityError:
                flash("Ese nombre de usuario ya existe.", "danger")

    users_rows = conn.execute(
        """
        SELECT u.*, d.name AS direction_name
        FROM users u
        LEFT JOIN directions d ON d.id = u.direction_id
        ORDER BY u.id DESC
        """
    ).fetchall()
    conn.close()
    return render_template("users.html", users=users_rows, directions=directions)


@app.route("/directions", methods=["GET", "POST"])
@login_required
@admin_required
def directions():
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        responsible_name = request.form.get("responsible_name", "").strip()
        email = request.form.get("email", "").strip()
        if not name:
            flash("El nombre de la dirección es obligatorio.", "danger")
        else:
            try:
                conn.execute(
                    "INSERT INTO directions(name, responsible_name, email, created_at) VALUES (?, ?, ?, ?)",
                    (name, responsible_name, email, now_iso()),
                )
                conn.commit()
                flash("Dirección registrada correctamente.", "success")
                return redirect(url_for("directions"))
            except sqlite3.IntegrityError:
                flash("La dirección ya existe.", "danger")

    directions_rows = conn.execute("SELECT * FROM directions ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("directions.html", directions=directions_rows)


@app.route("/reports")
@login_required
def reports():
    refresh_overdue_statuses()
    conn = get_db()
    if session.get("role") == "admin":
        rows = conn.execute(
            """
            SELECT a.*, d.name AS direction_name
            FROM activities a
            JOIN directions d ON d.id = a.direction_id
            ORDER BY d.name, a.due_date
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT a.*, d.name AS direction_name
            FROM activities a
            JOIN directions d ON d.id = a.direction_id
            WHERE a.direction_id = ?
            ORDER BY a.due_date
            """,
            (session.get("direction_id"),),
        ).fetchall()
    conn.close()
    return render_template(
        "reports.html", rows=rows, days_remaining=days_remaining, status_color=status_color
    )


@app.route("/dashboard-data")
@login_required
def dashboard_data():
    refresh_overdue_statuses()
    conn = get_db()
    if session.get("role") == "admin":
        progress_by_direction = conn.execute(
            """
            SELECT d.name AS label, COALESCE(ROUND(AVG(a.progress), 0), 0) AS value
            FROM directions d
            LEFT JOIN activities a ON a.direction_id = d.id
            GROUP BY d.id, d.name
            ORDER BY d.name
            """
        ).fetchall()
        status_counts = conn.execute(
            "SELECT status AS label, COUNT(*) AS value FROM activities GROUP BY status ORDER BY status"
        ).fetchall()
    else:
        progress_by_direction = conn.execute(
            """
            SELECT a.folio || ' - ' || a.title AS label, a.progress AS value
            FROM activities a
            WHERE a.direction_id = ?
            ORDER BY a.id DESC
            LIMIT 10
            """,
            (session.get("direction_id"),),
        ).fetchall()
        status_counts = conn.execute(
            """
            SELECT status AS label, COUNT(*) AS value
            FROM activities
            WHERE direction_id = ?
            GROUP BY status
            ORDER BY status
            """,
            (session.get("direction_id"),),
        ).fetchall()
    conn.close()

    return jsonify(
        {
            "progress": [dict(r) for r in progress_by_direction],
            "statuses": [dict(r) for r in status_counts],
        }
    )


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="No tienes permiso para entrar aquí."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="No encontramos lo que buscas."), 404

import os


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    init_db()

    # 👇 CREAR USUARIO ADMIN SI NO EXISTE
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", ("admin",)).fetchone()

    if not user:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", "admin123", "admin")
        )
        conn.commit()

    conn.close()

    app.run(debug=True, host="0.0.0.0", port=5000)