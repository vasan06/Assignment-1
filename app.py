import os
import sqlite3
import uuid
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE = BASE_DIR / "instance" / "app.sqlite3"
DEFAULT_UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "txt",
    "csv",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "zip",
}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        DATABASE=os.environ.get("DATABASE", str(DEFAULT_DATABASE)),
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER", str(DEFAULT_UPLOAD_FOLDER)),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )

    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    register_database(app)
    register_routes(app)

    with app.app_context():
        init_db()

    return app


def register_database(app):
    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    app.teardown_appcontext(close_db)
    app.get_db = get_db


def init_db():
    db = current_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            size INTEGER NOT NULL,
            content_type TEXT,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    db.commit()


def current_db():
    return current_app.get_db()


def register_routes(app):
    @app.context_processor
    def inject_user():
        return {"current_user": get_current_user()}

    @app.route("/")
    def home():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not name or not email or not password:
                flash("Name, email, and password are required.", "error")
            elif len(password) < 8:
                flash("Use at least 8 characters for your password.", "error")
            elif password != confirm_password:
                flash("Passwords do not match.", "error")
            else:
                try:
                    db = current_db()
                    cursor = db.execute(
                        """
                        INSERT INTO users (name, email, password_hash, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            name,
                            email,
                            generate_password_hash(password),
                            datetime.now(UTC).isoformat(timespec="seconds"),
                        ),
                    )
                    db.commit()
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    flash("Account created. Your workspace is ready.", "success")
                    return redirect(url_for("dashboard"))
                except sqlite3.IntegrityError:
                    flash("An account with that email already exists.", "error")

        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = current_db().execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                flash("Welcome back.", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "error")

        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        files = get_user_files(session["user_id"])
        total_bytes = sum(file["size"] for file in files)
        latest_upload = files[0]["uploaded_at"] if files else None
        return render_template(
            "dashboard.html",
            files=files,
            stats={
                "file_count": len(files),
                "total_size": format_bytes(total_bytes),
                "latest_upload": format_datetime(latest_upload) if latest_upload else "No uploads yet",
            },
            allowed_extensions=", ".join(sorted(ALLOWED_EXTENSIONS)),
        )

    @app.route("/upload", methods=["POST"])
    @login_required
    def upload():
        incoming_files = request.files.getlist("files")
        saved_count = 0

        for file_storage in incoming_files:
            if not file_storage or not file_storage.filename:
                continue

            if not allowed_file(file_storage.filename):
                flash(f"{file_storage.filename} is not an allowed file type.", "error")
                continue

            original_name = secure_filename(file_storage.filename)
            extension = original_name.rsplit(".", 1)[1].lower()
            stored_name = f"{uuid.uuid4().hex}.{extension}"
            destination = Path(app.config["UPLOAD_FOLDER"]) / stored_name
            file_storage.save(destination)
            size = destination.stat().st_size

            current_db().execute(
                """
                INSERT INTO files
                    (user_id, original_name, stored_name, size, content_type, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    original_name,
                    stored_name,
                    size,
                    file_storage.content_type,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
            saved_count += 1

        current_db().commit()

        if saved_count:
            flash(f"Uploaded {saved_count} file{'s' if saved_count != 1 else ''}.", "success")
        elif not incoming_files:
            flash("Choose at least one file to upload.", "error")

        return redirect(url_for("dashboard"))

    @app.route("/download/<int:file_id>")
    @login_required
    def download(file_id):
        file_record = get_owned_file(file_id)
        if not file_record:
            abort(404)

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            file_record["stored_name"],
            as_attachment=True,
            download_name=file_record["original_name"],
        )

    @app.route("/delete/<int:file_id>", methods=["POST"])
    @login_required
    def delete_file(file_id):
        file_record = get_owned_file(file_id)
        if not file_record:
            abort(404)

        target = Path(app.config["UPLOAD_FOLDER"]) / file_record["stored_name"]
        if target.exists():
            target.unlink()

        current_db().execute("DELETE FROM files WHERE id = ?", (file_id,))
        current_db().commit()
        flash(f"Deleted {file_record['original_name']}.", "success")
        return redirect(url_for("dashboard"))


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("Sign in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return current_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_files(user_id):
    rows = current_db().execute(
        """
        SELECT *
        FROM files
        WHERE user_id = ?
        ORDER BY uploaded_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    files = []
    for row in rows:
        file_record = dict(row)
        file_record["uploaded_label"] = format_datetime(file_record["uploaded_at"])
        file_record["size_label"] = format_bytes(file_record["size"])
        files.append(file_record)
    return files


def get_owned_file(file_id):
    return current_db().execute(
        "SELECT * FROM files WHERE id = ? AND user_id = ?",
        (file_id, session["user_id"]),
    ).fetchone()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def format_bytes(size):
    value = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def format_datetime(value):
    return datetime.fromisoformat(value).strftime("%d %b %Y, %H:%M")


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
