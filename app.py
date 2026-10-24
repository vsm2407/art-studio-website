
import os
from pathlib import Path
from functools import wraps
from datetime import timedelta
from datetime import date
from flask import abort

import mysql.connector
from mysql.connector import IntegrityError
from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# --------------------------------------------------
# 2. DATABASE CONNECTION
# --------------------------------------------------

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "art_studio"),
    )


# --------------------------------------------------
# 3. AUTHENTICATION AND AUTHORIZATION
# --------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Authentication required"}), 401

            if session.get("role") != required_role:
                return jsonify({"error": "Forbidden"}), 403

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


# --------------------------------------------------
# 4. HOME AND DATABASE HEALTH
# --------------------------------------------------

@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        database_name = cursor.fetchone()[0]
        cursor.close()

        return jsonify({
            "status": "ok",
            "database": database_name,
        })

    except mysql.connector.Error:
        app.logger.exception("Database health check failed")
        return jsonify({"error": "Database connection failed"}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 5. CUSTOMER REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in every field.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        connection = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (%s, %s, %s, 'customer')
                """,
                (name, email, password_hash),
            )

            connection.commit()
            user_id = cursor.lastrowid
            cursor.close()

            session.clear()
            session.permanent = True
            session["user_id"] = user_id
            session["name"] = name
            session["role"] = "customer"

            flash("Account created successfully!", "success")
            return redirect(url_for("dashboard"))

        except IntegrityError:
            if connection:
                connection.rollback()

            flash("An account with this email already exists.", "error")

        except mysql.connector.Error:
            if connection:
                connection.rollback()

            app.logger.exception("Registration failed")
            flash("Registration failed. Please try again.", "error")

        finally:
            if connection and connection.is_connected():
                connection.close()

    return render_template("register.html")


# --------------------------------------------------
# 6. LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        connection = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id, name, email, password_hash, role
                FROM users
                WHERE email = %s
                """,
                (email,),
            )

            user = cursor.fetchone()
            cursor.close()

            if user and check_password_hash(
                user["password_hash"], password
            ):
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["role"] = user["role"]

                flash("Welcome back!", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "error")

        except mysql.connector.Error:
            app.logger.exception("Login failed")
            flash("Login is temporarily unavailable.", "error")

        finally:
            if connection and connection.is_connected():
                connection.close()

    return render_template("login.html")


# --------------------------------------------------
# 7. LOGOUT
# --------------------------------------------------

@app.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# --------------------------------------------------
# 8. DASHBOARD
# --------------------------------------------------

@app.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=session)


# --------------------------------------------------
# 9. PAINTINGS CATALOGUE
# --------------------------------------------------

@app.get("/paintings")
@login_required
def paintings():
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, painting_code, title, artist, description,
                   price, image_path, status
            FROM paintings
            ORDER BY painting_code
            """
        )
        painting_list = cursor.fetchall()

        cursor.execute(
            """
            SELECT o.id AS order_id,
                   o.status AS order_status,
                   o.ordered_at,
                   p.title,
                   p.painting_code
            FROM painting_orders o
            JOIN paintings p ON p.id = o.painting_id
            WHERE o.customer_id = %s
            ORDER BY o.ordered_at DESC
            """,
            (session["user_id"],),
        )
        orders = cursor.fetchall()

        cursor.close()

        return render_template(
            "paintings.html",
            paintings=painting_list,
            orders=orders,
            user=session,
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load paintings")
        return "Could not load paintings. Please try again.", 500

    finally:
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 10. BUY A PAINTING
# --------------------------------------------------

@app.post("/paintings/<int:painting_id>/buy")
@login_required
def buy_painting(painting_id):
    if session.get("role") != "customer":
        return jsonify({"error": "Only customers can buy paintings"}), 403

    connection = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Lock the painting before checking its availability.
        cursor.execute(
            """
            SELECT id, title, status
            FROM paintings
            WHERE id = %s
            FOR UPDATE
            """,
            (painting_id,),
        )
        painting = cursor.fetchone()

        if not painting:
            connection.rollback()
            flash("Painting not found.", "error")
            return redirect(url_for("paintings"))

        if painting["status"] != "available":
            connection.rollback()
            flash(
                "Sorry, this painting has already been sold.",
                "error",
            )
            return redirect(url_for("paintings"))

        cursor.execute(
            """
            INSERT INTO painting_orders
                (customer_id, painting_id, status)
            VALUES (%s, %s, 'placed')
            """,
            (session["user_id"], painting_id),
        )

        cursor.execute(
            """
            UPDATE paintings
            SET status = 'sold'
            WHERE id = %s AND status = 'available'
            """,
            (painting_id,),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            flash("Painting is no longer available.", "error")
            return redirect(url_for("paintings"))

        connection.commit()

        flash(
            f"You purchased '{painting['title']}' successfully!",
            "success",
        )
        return redirect(url_for("paintings"))

    except mysql.connector.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Painting purchase failed")
        flash(
            "The purchase could not be completed. Please try again.",
            "error",
        )
        return redirect(url_for("paintings"))

    finally:
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 11. CANCEL A PAINTING ORDER
# --------------------------------------------------

@app.post("/orders/<int:order_id>/cancel")
@login_required
def cancel_painting_order(order_id):
    if session.get("role") != "customer":
        return jsonify({"error": "Only customers can cancel orders"}), 403

    connection = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        # Customers can only access their own orders.
        cursor.execute(
            """
            SELECT o.id, o.painting_id, o.status, p.title
            FROM painting_orders o
            JOIN paintings p ON p.id = o.painting_id
            WHERE o.id = %s AND o.customer_id = %s
            FOR UPDATE
            """,
            (order_id, session["user_id"]),
        )
        order = cursor.fetchone()

        if not order:
            connection.rollback()
            flash("Order not found.", "error")
            return redirect(url_for("paintings"))

        if order["status"] != "placed":
            connection.rollback()
            flash("This order can no longer be cancelled.", "error")
            return redirect(url_for("paintings"))

        cursor.execute(
            """
            UPDATE paintings
            SET status = 'available'
            WHERE id = %s AND status = 'sold'
            """,
            (order["painting_id"],),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            flash(
                "Painting status changed. Refresh and try again.",
                "error",
            )
            return redirect(url_for("paintings"))

        cursor.execute(
            """
            UPDATE painting_orders
            SET status = 'cancelled',
                cancelled_at = CURRENT_TIMESTAMP
            WHERE id = %s
              AND customer_id = %s
              AND status = 'placed'
            """,
            (order_id, session["user_id"]),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            flash("Order could not be cancelled.", "error")
            return redirect(url_for("paintings"))

        connection.commit()

        flash(
            f"Order cancelled. '{order['title']}' is available again.",
            "success",
        )
        return redirect(url_for("paintings"))

    except mysql.connector.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Order cancellation failed")
        flash("Cancellation failed. Please try again.", "error")
        return redirect(url_for("paintings"))

    finally:
        if connection and connection.is_connected():
            connection.close()


# --------------------------------------------------
# WALL-PAINTING BOOKINGS
# --------------------------------------------------

from datetime import date, timedelta


def ensure_wall_booking_date_constraint(connection):
    """Allow a cancelled booking's date to be booked again.

    The original schema has UNIQUE(booking_date), which also blocks a date
    after its booking is cancelled. This migration replaces that constraint
    with a unique generated column that is NULL only for cancelled bookings.
    MySQL permits multiple NULL values in a unique index.
    Safe to call repeatedly.
    """
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wall_painting_bookings'
              AND COLUMN_NAME = 'active_booking_date'
        """)
        active_column_exists = cursor.fetchone() is not None

        if not active_column_exists:
            # Remove the old single-column unique index on booking_date.
            cursor.execute("""
                SELECT INDEX_NAME
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'wall_painting_bookings'
                  AND COLUMN_NAME = 'booking_date'
                  AND NON_UNIQUE = 0
                  AND INDEX_NAME <> 'PRIMARY'
            """)
            indexes = cursor.fetchall()
            for index in indexes:
                # Only remove a unique index if booking_date is its sole column.
                cursor.execute("""
                    SELECT COUNT(*) AS column_count
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'wall_painting_bookings'
                      AND INDEX_NAME = %s
                """, (index['INDEX_NAME'],))
                index_info = cursor.fetchone()
                if index_info and index_info['column_count'] == 1:
                    safe_index_name = index['INDEX_NAME'].replace('`', '``')
                    cursor.execute(
                        f"ALTER TABLE wall_painting_bookings DROP INDEX `{safe_index_name}`"
                    )

            cursor.execute("""
                ALTER TABLE wall_painting_bookings
                ADD COLUMN active_booking_date DATE
                GENERATED ALWAYS AS (
                    CASE WHEN status = 'cancelled' THEN NULL ELSE booking_date END
                ) STORED
            """)

        cursor.execute("""
            SELECT INDEX_NAME
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'wall_painting_bookings'
              AND INDEX_NAME = 'uq_active_booking_date'
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE wall_painting_bookings
                ADD UNIQUE KEY uq_active_booking_date (active_booking_date)
            """)
    finally:
        cursor.close()


@app.get("/wall-painting")
@login_required
def wall_painting():
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, customer_id, booking_date, area_sqft,
                   address, rate_per_sqft, total_price, status, created_at
            FROM wall_painting_bookings
            WHERE customer_id = %s
            ORDER BY booking_date DESC
        """, (session["user_id"],))

        bookings = cursor.fetchall()
        cursor.close()

        today = date.today()

        return render_template(
            "wall_painting.html",
            bookings=bookings,
            min_date=(today + timedelta(days=7)).isoformat(),
            max_date=(today + timedelta(days=90)).isoformat(),
            user=session,
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load wall-painting bookings")
        return "Could not load bookings. Please try again.", 500

    finally:
        if connection and connection.is_connected():
            connection.close()


@app.post("/wall-painting/book")
@login_required
def create_wall_booking():
    if session.get("role") != "customer":
        return jsonify({"error": "Only customers can book wall painting"}), 403

    raw_date = request.form.get("booking_date", "").strip()
    raw_area = request.form.get("area_sqft", "").strip()
    address = request.form.get("address", "").strip()

    try:
        booking_date = date.fromisoformat(raw_date)
        area_sqft = int(raw_area)
    except (ValueError, TypeError):
        flash("Enter a valid date and area.", "error")
        return redirect(url_for("wall_painting"))

    days_ahead = (booking_date - date.today()).days

    if not 7 <= days_ahead <= 90:
        flash("Choose a date between 7 and 90 days from today.", "error")
        return redirect(url_for("wall_painting"))

    if not 10 <= area_sqft <= 500:
        flash("Area must be between 10 and 500 square feet.", "error")
        return redirect(url_for("wall_painting"))

    if not address or len(address) > 2000:
        flash("Enter a valid painting address.", "error")
        return redirect(url_for("wall_painting"))

    connection = None

    try:
        connection = get_db_connection()
        # Upgrade the old UNIQUE(booking_date) constraint so cancelled dates
        # become available again. This function is safe to run repeatedly.
        ensure_wall_booking_date_constraint(connection)
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO wall_painting_bookings
                (customer_id, booking_date, area_sqft, address, rate_per_sqft)
            VALUES (%s, %s, %s, %s, 150.00)
        """, (
            session["user_id"],
            booking_date,
            area_sqft,
            address,
        ))

        connection.commit()
        flash(
            f"Booking requested! Estimated price: ₹{area_sqft * 150:,.2f}.",
            "success",
        )

    except IntegrityError:
        if connection:
            connection.rollback()
        flash("That date has already been booked. Please choose another date.", "error")

    except mysql.connector.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Could not create wall-painting booking")
        flash("Booking failed. Please try again.", "error")

    finally:
        if connection and connection.is_connected():
            connection.close()

    return redirect(url_for("wall_painting"))


@app.post("/wall-painting/<int:booking_id>/cancel")
@login_required
def cancel_wall_booking(booking_id):
    if session.get("role") != "customer":
        return jsonify({"error": "Only customers can cancel bookings"}), 403

    connection = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, booking_date, status
            FROM wall_painting_bookings
            WHERE id = %s AND customer_id = %s
            FOR UPDATE
        """, (booking_id, session["user_id"]))

        booking = cursor.fetchone()

        if not booking:
            connection.rollback()
            flash("Booking not found.", "error")
            return redirect(url_for("wall_painting"))

        days_until_booking = (booking["booking_date"] - date.today()).days

        if booking["status"] not in ("requested", "confirmed"):
            connection.rollback()
            flash("This booking can no longer be cancelled.", "error")
            return redirect(url_for("wall_painting"))

        if days_until_booking < 3:
            connection.rollback()
            flash("Bookings can only be cancelled at least 3 days in advance.", "error")
            return redirect(url_for("wall_painting"))

        cursor.execute("""
            UPDATE wall_painting_bookings
            SET status = 'cancelled'
            WHERE id = %s AND customer_id = %s
        """, (booking_id, session["user_id"]))

        connection.commit()
        flash("Wall-painting booking cancelled.", "success")

    except mysql.connector.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Could not cancel wall-painting booking")
        flash("Cancellation failed. Please try again.", "error")

    finally:
        if connection and connection.is_connected():
            connection.close()

    return redirect(url_for("wall_painting"))


# --------------------------------------------------
# ADMIN: WALL-PAINTING BOOKING MANAGEMENT
# --------------------------------------------------

@app.get("/admin/bookings")
@login_required
def admin_bookings():
    if session.get("role") != "admin":
        return "Forbidden: admin access required.", 403

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, customer_id, booking_date, area_sqft,
                   address, rate_per_sqft, total_price,
                   status, created_at
            FROM wall_painting_bookings
            ORDER BY created_at DESC
        """)

        bookings = cursor.fetchall()
        cursor.close()

        return render_template(
            "admin_bookings.html",
            bookings=bookings
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load admin bookings")
        return "Could not load bookings.", 500

    finally:
        if connection and connection.is_connected():
            connection.close()


@app.post("/admin/bookings/<int:booking_id>/status")
@login_required
def update_booking_status(booking_id):
    if session.get("role") != "admin":
        return "Forbidden: admin access required.", 403

    new_status = request.form.get("status", "").strip()

    if new_status not in ("confirmed", "declined"):
        return "Invalid booking status.", 400

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE wall_painting_bookings
            SET status = %s
            WHERE id = %s AND status = 'requested'
        """, (new_status, booking_id))

        updated = cursor.rowcount
        connection.commit()
        cursor.close()

        if updated == 0:
            flash(
                "Booking not found or it has already been processed.",
                "error"
            )
        else:
            flash(f"Booking #{booking_id} {new_status}.", "success")

    except mysql.connector.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Could not update booking status")
        flash("Could not update the booking.", "error")

    finally:
        if connection and connection.is_connected():
            connection.close()

    return redirect(url_for("admin_bookings"))


# --------------------------------------------------
# POTTERY REQUESTS - CUSTOMER
# --------------------------------------------------

@app.route("/pottery", methods=["GET", "POST"])
@login_required
def pottery():
    if session.get("role") != "customer":
        abort(403)

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":
            try:
                item_id = int(request.form.get("item_id", ""))
                glaze_id = int(request.form.get("glaze_id", ""))
                quantity = int(request.form.get("quantity", ""))
                needed_by = date.fromisoformat(
                    request.form.get("needed_by", "")
                )
            except (ValueError, TypeError):
                flash("Please enter valid pottery request details.", "error")
                return redirect(url_for("pottery"))

            if not 1 <= quantity <= 12:
                flash("Quantity must be between 1 and 12.", "error")
                return redirect(url_for("pottery"))

            if (needed_by - date.today()).days < 14:
                flash("The required-by date must be at least 14 days away.", "error")
                return redirect(url_for("pottery"))

            cursor.execute(
                "SELECT id FROM pottery_items WHERE id = %s",
                (item_id,)
            )
            item = cursor.fetchone()

            cursor.execute(
                "SELECT id FROM pottery_glazes WHERE id = %s",
                (glaze_id,)
            )
            glaze = cursor.fetchone()

            if not item or not glaze:
                flash("Please select a valid pottery item and glaze.", "error")
                return redirect(url_for("pottery"))

            cursor.execute("""
                INSERT INTO pottery_requests
                    (customer_id, item_id, glaze_id, quantity, needed_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (session["user_id"], item_id, glaze_id, quantity, needed_by))

            connection.commit()
            flash("Your pottery request has been submitted.", "success")
            return redirect(url_for("pottery"))

        cursor.execute("SELECT id, item_name FROM pottery_items ORDER BY id")
        items = cursor.fetchall()

        # Read the glaze name column from the existing table.
        cursor.execute("SELECT * FROM pottery_glazes ORDER BY id")
        raw_glazes = cursor.fetchall()
        glazes = []

        for glaze_row in raw_glazes:
            name_key = next(
                (key for key in glaze_row if key != "id"),
                None
            )
            glazes.append({
                "id": glaze_row["id"],
                "glaze_name": glaze_row[name_key] if name_key else ""
            })

        cursor.execute("""
            SELECT pr.*, pi.item_name
            FROM pottery_requests pr
            JOIN pottery_items pi ON pi.id = pr.item_id
            WHERE pr.customer_id = %s
            ORDER BY pr.created_at DESC
        """, (session["user_id"],))
        requests_list = cursor.fetchall()

        glaze_names = {g["id"]: g["glaze_name"] for g in glazes}
        for pottery_request in requests_list:
            pottery_request["glaze_name"] = glaze_names.get(
                pottery_request["glaze_id"], "Unknown"
            )

        return render_template(
            "pottery.html",
            items=items,
            glazes=glazes,
            requests=requests_list,
            today_plus_14=date.today().fromordinal(
                date.today().toordinal() + 14
            ).isoformat()
        )

    except mysql.connector.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Pottery request operation failed")
        return "Could not process pottery requests.", 500

    finally:
        if connection and connection.is_connected():
            connection.close()


@app.post("/pottery/<int:request_id>/edit")
@login_required
def edit_pottery_request(request_id):
    if session.get("role") != "customer":
        abort(403)

    try:
        item_id = int(request.form.get("item_id", ""))
        glaze_id = int(request.form.get("glaze_id", ""))
        quantity = int(request.form.get("quantity", ""))
        needed_by = date.fromisoformat(request.form.get("needed_by", ""))
    except (ValueError, TypeError):
        flash("Please enter valid request details.", "error")
        return redirect(url_for("pottery"))

    if not 1 <= quantity <= 12:
        flash("Quantity must be between 1 and 12.", "error")
        return redirect(url_for("pottery"))

    if (needed_by - date.today()).days < 14:
        flash("The required-by date must be at least 14 days away.", "error")
        return redirect(url_for("pottery"))

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE pottery_requests
            SET item_id = %s, glaze_id = %s,
                quantity = %s, needed_by = %s
            WHERE id = %s AND customer_id = %s
              AND status = 'requested'
              AND EXISTS (SELECT id FROM pottery_items WHERE id = %s)
              AND EXISTS (SELECT id FROM pottery_glazes WHERE id = %s)
        """, (
            item_id, glaze_id, quantity, needed_by,
            request_id, session["user_id"], item_id, glaze_id
        ))

        changed = cursor.rowcount
        connection.commit()
        cursor.close()

        if changed:
            flash("Pottery request updated.", "success")
        else:
            flash("Request not found or no longer editable.", "error")

    except mysql.connector.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Pottery request edit failed")
        flash("Could not update the request.", "error")

    finally:
        if connection and connection.is_connected():
            connection.close()

    return redirect(url_for("pottery"))


@app.post("/pottery/<int:request_id>/cancel")
@login_required
def cancel_pottery_request(request_id):
    if session.get("role") != "customer":
        abort(403)

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE pottery_requests
            SET status = 'cancelled'
            WHERE id = %s AND customer_id = %s
              AND status = 'requested'
        """, (request_id, session["user_id"]))

        changed = cursor.rowcount
        connection.commit()
        cursor.close()

        flash(
            "Pottery request cancelled." if changed
            else "Request not found or no longer cancellable.",
            "success" if changed else "error"
        )

    except mysql.connector.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Pottery request cancellation failed")
        flash("Could not cancel the request.", "error")

    finally:
        if connection and connection.is_connected():
            connection.close()

    return redirect(url_for("pottery"))


# --------------------------------------------------
# POTTERY REQUESTS - ADMIN
# --------------------------------------------------

@app.get("/admin/pottery")
@login_required
def admin_pottery():
    if session.get("role") != "admin":
        abort(403)

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT pr.*, pi.item_name, u.name AS customer_name
            FROM pottery_requests pr
            JOIN pottery_items pi ON pi.id = pr.item_id
            JOIN users u ON u.id = pr.customer_id
            ORDER BY pr.created_at DESC
        """)
        requests_list = cursor.fetchall()

        cursor.execute("SELECT * FROM pottery_glazes")
        raw_glazes = cursor.fetchall()
        glaze_names = {}

        for glaze_row in raw_glazes:
            name_key = next(
                (key for key in glaze_row if key != "id"),
                None
            )
            glaze_names[glaze_row["id"]] = (
                glaze_row[name_key] if name_key else "Unknown"
            )

        for pottery_request in requests_list:
            pottery_request["glaze_name"] = glaze_names.get(
                pottery_request["glaze_id"], "Unknown"
            )

        return render_template(
            "admin_pottery.html",
            requests=requests_list
        )

    except mysql.connector.Error:
        app.logger.exception("Could not load admin pottery requests")
        return "Could not load pottery requests.", 500

    finally:
        if connection and connection.is_connected():
            connection.close()


@app.post("/admin/pottery/<int:request_id>/status")
@login_required
def update_pottery_status(request_id):
    if session.get("role") != "admin":
        abort(403)

    new_status = request.form.get("status", "")
    if new_status not in ("accepted", "declined"):
        abort(400)

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE pottery_requests
            SET status = %s
            WHERE id = %s AND status = 'requested'
        """, (new_status, request_id))

        changed = cursor.rowcount
        connection.commit()
        cursor.close()

        flash(
            f"Request #{request_id} {new_status}." if changed
            else "Request not found or already processed.",
            "success" if changed else "error"
        )

    except mysql.connector.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Could not update pottery status")
        flash("Could not update the request.", "error")

    finally:
        if connection and connection.is_connected():
            connection.close()

    return redirect(url_for("admin_pottery"))

# --------------------------------------------------
# 12. START THE APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
