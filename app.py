# admin = admin@gmail.com ; password = admin123
# for employees (email before @ + 123)
import os
import mysql.connector
from mysql.connector import Error
import time
import csv
from io import StringIO, BytesIO
from flask import Flask, render_template, request, redirect, session, send_file, flash, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret"  # change for production

DB = "laundry.db"
UPLOAD_DIR = "static/emp_photos"
ALLOWED = {"png", "jpg", "jpeg", "gif"}

# ensure upload folder exists and is a directory
if os.path.exists(UPLOAD_DIR) and not os.path.isdir(UPLOAD_DIR):
    try:
        os.remove(UPLOAD_DIR)
    except Exception:
        pass
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- DB helpers ----------
def get_db():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="laundry_db"
    )
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor(dictionary=True)

    # create tables
    c.execute("""
        CREATE TABLE IF NOT EXISTS users(
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(100),
        role VARCHAR(20),
        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS customers(
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    mobile VARCHAR(20),
    address TEXT,
    email VARCHAR(100) UNIQUE,
    password TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
  
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories(
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100)
        )
    """)
    c.execute("""
CREATE TABLE IF NOT EXISTS clothes(
    id INT AUTO_INCREMENT PRIMARY KEY,
    cloth_name VARCHAR(100),
    price INT
)
""")

    c.execute("""
        CREATE TABLE IF NOT EXISTS employees(
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100),
            mobile VARCHAR(20),
            email VARCHAR(100),
            address TEXT,
            photo TEXT,
            password TEXT,
            is_busy INT DEFAULT 0
        )
    """)

    c.execute("""
CREATE TABLE IF NOT EXISTS bookings(
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    category_id INT,
    date VARCHAR(50),
    status VARCHAR(50) DEFAULT 'Pending',
    employee_id INT,
    cancelled_flag INT DEFAULT 0,
    task_status VARCHAR(50) DEFAULT 'Assigned'
)
""")
    c.execute("""
CREATE TABLE IF NOT EXISTS booking_items(
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT,
    cloth_id INT,
    quantity INT,
    price INT,
    total_cost INT
)
""")

    conn.commit()


    c.close()
    conn.close()



init_db()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED


def save_photo(fileobj):
    if not fileobj or fileobj.filename == "":
        return ""
    ext = fileobj.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return ""
    fname = secure_filename(str(int(time.time())) + "_" + fileobj.filename)
    full = os.path.join(UPLOAD_DIR, fname)
    fileobj.save(full)
    return fname


def remove_photo(fname):
    if not fname:
        return
    p = os.path.join(UPLOAD_DIR, fname)
    try:
        if os.path.exists(p):
            os.remove(p)
    except:
        pass


def download_csv_from_rows(rows, columns, filename):
    out = StringIO()
    w = csv.writer(out)
    w.writerow(columns)
    for r in rows:
        row = []
        for col in columns:
            row.append(r[col] if col in r.keys() else "")
        w.writerow(row)
    mem = BytesIO(out.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, download_name=filename, as_attachment=True)


# ---------- Routes ----------

@app.route("/")
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    pwd = request.form.get("password", "")

    conn = get_db()
    c = conn.cursor(dictionary=True)


        # 1️⃣ Check Admin login
    if email == "admin@gmail.com" and pwd == "admin123":
        session["role"] = "admin"

        # store login history
        c.execute("INSERT INTO users(email, role) VALUES(%s,%s)",
                (email, "admin"))
        conn.commit()

        c.close()
        conn.close()
        return redirect("/admin")


    # 2️⃣ Check Customer login
    c.execute("SELECT * FROM customers WHERE email=%s", (email,))
    cust = c.fetchone()

    if cust and check_password_hash(cust["password"], pwd):
        session["user_id"] = cust["id"]
        session["role"] = "user"

        # store login history
        c.execute("INSERT INTO users(email, role) VALUES(%s,%s)",
                (email, "user"))
        conn.commit()

        c.close()
        conn.close()
        return redirect("/dashboard")


    # 3️⃣ Check Employee login
    c.execute("SELECT * FROM employees WHERE email=%s", (email,))
    emp = c.fetchone()

    if emp and check_password_hash(emp["password"], pwd):
        session["emp_id"] = emp["id"]
        session["role"] = "employee"

        # store login history
        c.execute("INSERT INTO users(email, role) VALUES(%s,%s)",
                (email, "employee"))
        conn.commit()

        c.close()
        conn.close()
        return redirect("/employee")
    flash("Invalid Email or Password")
    c.close()
    conn.close()
    return redirect("/")




@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "GET":
        return render_template("register.html")
    name = request.form.get("name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    address = request.form.get("address", "").strip()
    email = request.form.get("email", "").strip()
    pwd = request.form.get("password", "")
    if not (name and mobile and address and email and pwd):
        flash("Fill all fields")
        return redirect("/register")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    try:
        c.execute("INSERT INTO customers(name,mobile,address,email,password) VALUES(%s,%s,%s,%s,%s)",
                  (name, mobile, address, email, generate_password_hash(pwd)))
        conn.commit()
       


    except Error:
        flash("Email already used")
        c.close()
        return redirect("/register")
    c.close()
    conn.close()

    flash("Account created — login now")
    return redirect("/")


# ---------- User Routes ----------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM categories ORDER BY id")
    cats = c.fetchall()
    c.execute("SELECT * FROM clothes")
    clothes = c.fetchall()
    c.close()
    conn.close()

    return render_template("user_dashboard.html", categories=cats, clothes=clothes)

@app.route("/book", methods=["POST"])
def book():

    if "user_id" not in session:
        return redirect("/")

    uid = session["user_id"]
    cat = request.form.get("category")
    cloths = request.form.getlist("cloth[]")
    qtys = request.form.getlist("qty[]")
    date = request.form.get("date")

    # prevent empty booking
    if not any(qtys):
        flash("Please enter quantity for at least one cloth")
        return redirect("/dashboard")

    if not (cat and date):
        flash("Select category & date")
        return redirect("/dashboard")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # create booking
    c.execute(
        "INSERT INTO bookings(user_id,category_id,date) VALUES(%s,%s,%s)",
        (uid, cat, date)
    )

    booking_id = c.lastrowid

    # insert clothes
    for cloth, qty in zip(cloths, qtys):

        if not cloth or not qty:
            continue

        qty = int(qty)

        if qty <= 0:
            continue

        c.execute("SELECT price FROM clothes WHERE id=%s", (cloth,))
        p = c.fetchone()

        if not p:
            continue

        price = int(p["price"])
        total = price * qty

        c.execute("""
            INSERT INTO booking_items
            (booking_id,cloth_id,quantity,price,total_cost)
            VALUES(%s,%s,%s,%s,%s)
        """, (booking_id, cloth, qty, price, total))

    conn.commit()

    c.close()
    conn.close()

    flash("Booking created")
    return redirect("/my_bookings")
@app.route("/my_bookings")
def my_bookings():
    if "user_id" not in session:
        return redirect("/")

    uid = session["user_id"]

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # get bookings
    c.execute("""
        SELECT b.*, cat.name AS category,
               e.name AS emp_name, e.mobile AS emp_mobile,
               e.email AS emp_email, e.address AS emp_address,
               e.photo AS emp_photo
        FROM bookings b
        LEFT JOIN categories cat ON cat.id=b.category_id
        LEFT JOIN employees e ON e.id=b.employee_id
        WHERE b.user_id=%s
        ORDER BY b.id DESC
    """, (uid,))

    bookings = c.fetchall()

    # get clothes for each booking
    for b in bookings:

        c.execute("""
            SELECT bi.*, cl.cloth_name
            FROM booking_items bi
            JOIN clothes cl ON cl.id = bi.cloth_id
            WHERE bi.booking_id=%s
        """, (b["id"],))

        b["items"] = c.fetchall()

    c.close()
    conn.close()

    return render_template("user_bookings.html", bookings=bookings)
@app.route("/edit_booking/<int:bid>", methods=["GET"])
def edit_booking_page(bid):

    if "user_id" not in session:
        return redirect("/")

    uid = session["user_id"]

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM bookings WHERE id=%s AND user_id=%s", (bid, uid))
    b = c.fetchone()

    if not b:
        flash("Booking not found")
        return redirect("/my_bookings")

    if b["status"] != "Pending":
        flash("Cannot edit booking after it has been processed.")
        return redirect("/my_bookings")

    # categories
    c.execute("SELECT * FROM categories")
    cats = c.fetchall()

    # clothes
    c.execute("SELECT * FROM clothes")
    clothes = c.fetchall()

    # selected items
    c.execute("""
        SELECT bi.*, cl.cloth_name
        FROM booking_items bi
        JOIN clothes cl ON cl.id=bi.cloth_id
        WHERE booking_id=%s
    """, (bid,))
    items = c.fetchall()

    c.close()
    conn.close()

    return render_template(
        "edit_booking.html",
        b=b,
        categories=cats,
        clothes=clothes,
        items=items
    )



@app.route("/update_booking_user/<int:bid>", methods=["POST"])
def update_booking_user(bid):

    if "user_id" not in session:
        return redirect("/")

    uid = session["user_id"]
    cat = request.form.get("category")
    cloths = request.form.getlist("cloth[]")
    qtys = request.form.getlist("qty[]")
    date = request.form.get("date")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # check booking
    c.execute("SELECT * FROM bookings WHERE id=%s AND user_id=%s", (bid, uid))
    b = c.fetchone()

    if not b:
        flash("Booking not found")
        c.close()
        conn.close()
        return redirect("/my_bookings")

    if b["status"] != "Pending":
        flash("Cannot edit booking after it has been processed.")
        c.close()
        conn.close()
        return redirect("/my_bookings")

    # update main booking
    c.execute(
        "UPDATE bookings SET category_id=%s, date=%s WHERE id=%s",
        (cat, date, bid)
    )

    # delete old clothes
    c.execute("DELETE FROM booking_items WHERE booking_id=%s", (bid,))

    # insert new clothes
    for cloth, qty in zip(cloths, qtys):

        if not cloth or not qty:
            continue

        qty = int(qty)

        if qty <= 0:
            continue

        c.execute("SELECT price FROM clothes WHERE id=%s", (cloth,))
        p = c.fetchone()

        if not p:
            continue

        price = int(p["price"])
        total = price * qty

        c.execute("""
        INSERT INTO booking_items
        (booking_id,cloth_id,quantity,price,total_cost)
        VALUES(%s,%s,%s,%s,%s)
        """, (bid, cloth, qty, price, total))

    conn.commit()

    c.close()
    conn.close()

    flash("Booking updated successfully")
    return redirect("/my_bookings")


@app.route("/cancel/<int:bid>")
def cancel(bid):
    if "user_id" not in session:
        return redirect("/")
    uid = session["user_id"]
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT status FROM bookings WHERE id=%s AND user_id=%s", (bid, uid))
    b=c.fetchone()
    if not b:
        c.close()
        flash("Booking not found")
        return redirect("/my_bookings")
    if b["status"] != "Pending":
        c.close()
        flash("Cannot cancel booking after it has been accepted/processed.")
        return redirect("/my_bookings")
    c.execute("UPDATE bookings SET status='Cancelled (User)', cancelled_flag=1 WHERE id=%s AND user_id=%s", (bid, uid))
    conn.commit()

    c.close()
    conn.close()

    flash("Booking cancelled")
    return redirect("/my_bookings")


@app.route("/employees")
def user_employees():
    if "user_id" not in session:
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM employees ORDER BY name")
    emps=c.fetchall()
    c.close()
    conn.close()

    return render_template("user_employees.html", employees=emps)

# ---------- Employee Routes ----------

@app.route("/employee")
def employee_dashboard():

    if session.get("role") != "employee":
        return redirect("/")

    eid = session["emp_id"]

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("""
    SELECT b.*, 
           u.name AS uname, 
           u.address,
           cat.name AS category
    FROM bookings b
    JOIN customers u ON u.id = b.user_id
    LEFT JOIN categories cat ON cat.id = b.category_id
    WHERE b.employee_id = %s
    """, (eid,))

    tasks = c.fetchall()

    # get clothes and calculate total
    for t in tasks:

        c.execute("""
            SELECT bi.*, cl.cloth_name
            FROM booking_items bi
            JOIN clothes cl ON cl.id=bi.cloth_id
            WHERE bi.booking_id=%s
        """, (t["id"],))

        items = c.fetchall()

        t["items"] = items

        total = 0
        for i in items:
            total += i["total_cost"]

        t["total_cost"] = total

    c.close()
    conn.close()

    return render_template("employee_dashboard.html", tasks=tasks)

@app.route("/employee/accept/<int:bid>")
def employee_accept(bid):

    if session.get("role") != "employee":
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # check status first
    c.execute("SELECT task_status FROM bookings WHERE id=%s", (bid,))
    status = c.fetchone()

    if status and status["task_status"] == "Delivered":
        flash("Task already completed. Cannot modify again.")
        c.close()
        conn.close()
        return redirect("/employee")

    c.execute("UPDATE bookings SET task_status='Accepted' WHERE id=%s", (bid,))
    conn.commit()

    c.close()
    conn.close()

    return redirect("/employee")


@app.route("/employee/pick/<int:bid>")
def employee_pick(bid):

    if session.get("role") != "employee":
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT task_status FROM bookings WHERE id=%s", (bid,))
    status = c.fetchone()

    if status and status["task_status"] == "Delivered":
        flash("Task already completed. Cannot modify again.")
        c.close()
        conn.close()
        return redirect("/employee")

    c.execute("UPDATE bookings SET task_status='Picked Up' WHERE id=%s", (bid,))
    conn.commit()

    c.close()
    conn.close()

    return redirect("/employee")

@app.route("/employee/complete/<int:bid>")
def employee_complete(bid):

    if session.get("role") != "employee":
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT task_status FROM bookings WHERE id=%s", (bid,))
    status = c.fetchone()

    if status and status["task_status"] == "Delivered":
        flash("Task already completed. Cannot modify again.")
        c.close()
        conn.close()
        return redirect("/employee")

    c.execute("UPDATE bookings SET task_status='Completed' WHERE id=%s", (bid,))
    conn.commit()

    c.close()
    conn.close()

    return redirect("/employee")

@app.route("/employee/deliver/<int:bid>")
def employee_deliver(bid):

    if session.get("role") != "employee":
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # Check current status
    c.execute("SELECT task_status, employee_id FROM bookings WHERE id=%s", (bid,))
    booking = c.fetchone()

    if not booking:
        c.close()
        conn.close()
        return redirect("/employee")

    if booking["task_status"] == "Delivered":
        flash("Task already completed. Cannot modify again.")
        c.close()
        conn.close()
        return redirect("/employee")

    # 1️⃣ Update booking
    c.execute("""
        UPDATE bookings
        SET task_status='Delivered', status='Completed'
        WHERE id=%s
    """, (bid,))

    # 2️⃣ Make employee FREE again
    c.execute("""
        UPDATE employees
        SET is_busy=0
        WHERE id=%s
    """, (booking["employee_id"],))

    conn.commit()
    c.close()
    conn.close()

    return redirect("/employee")

@app.route("/admin/clothes")
def admin_clothes():
    if not admin_only():
        return redirect("/")

    conn=get_db()
    c=conn.cursor(dictionary=True)

    c.execute("SELECT * FROM clothes")
    clothes=c.fetchall()

    c.close()
    conn.close()

    return render_template("admin_clothes.html", clothes=clothes)


@app.route("/add_cloth", methods=["POST"])
def add_cloth():

    if not admin_only():
        return redirect("/")

    name=request.form.get("name")
    price=request.form.get("price")

    conn=get_db()
    c=conn.cursor()

    c.execute("INSERT INTO clothes(cloth_name,price) VALUES(%s,%s)",(name,price))
    conn.commit()

    c.close()
    conn.close()

    return redirect("/admin/clothes")


@app.route("/delete_cloth/<int:id>")
def delete_cloth(id):

    if not admin_only():
        return redirect("/")

    conn=get_db()
    c=conn.cursor()

    c.execute("DELETE FROM clothes WHERE id=%s",(id,))
    conn.commit()

    c.close()
    conn.close()

    return redirect("/admin/clothes")


# ---------- Admin helpers ----------
def admin_only():
    return session.get("role") == "admin"


# ---------- Admin Routes ----------
@app.route("/admin")
def admin_dashboard():
    if not admin_only():
        return redirect("/")
    return render_template("admin_dashboard.html")


# categories: add / delete only
@app.route("/admin/categories")
def admin_categories():
    if not admin_only():
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM categories ORDER BY id")
    cats=c.fetchall()
    c.close()
    conn.close()

    return render_template("admin_categories.html", categories=cats)


@app.route("/add_category", methods=["POST"])
def add_category():
    if not admin_only():
        return redirect("/")
    name = request.form.get("category", "").strip()
    if name:
        conn = get_db()
        c = conn.cursor(dictionary=True)

        c.execute("INSERT INTO categories(name) VALUES(%s)", (name,))
        conn.commit()

        c.close()
        conn.close()

        flash("Category added")
    return redirect("/admin/categories")


@app.route("/delete_category/<int:cid>")
def delete_category(cid):
    if not admin_only():
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("DELETE FROM categories WHERE id=%s", (cid,))
    conn.commit()

    c.close()
    conn.close()

    flash("Category deleted")
    return redirect("/admin/categories")


# employees: admin can add / edit / delete
@app.route("/admin/employees")
def admin_employees():
    if not admin_only():
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM employees ORDER BY id DESC")
    emps=c.fetchall()
    c.close()
    conn.close()

    return render_template("admin_employees.html", employees=emps)


@app.route("/add_employee", methods=["POST"])
def add_employee():
    if not admin_only():
        return redirect("/")

    name = request.form.get("name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    photo = request.files.get("photo")

    photo_name = save_photo(photo) if photo and photo.filename else ""

    raw_pwd = email.split("@")[0] + "123"
    hashed_pwd = generate_password_hash(raw_pwd)

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("""
        INSERT INTO employees(name,mobile,email,address,photo,password,is_busy)
        VALUES(%s,%s,%s,%s,%s,%s,0)
    """, (name, mobile, email, address, photo_name, hashed_pwd))

    conn.commit()

    c.close()
    conn.close()


    flash(f"Employee added. Password: {raw_pwd}")
    return redirect("/admin/employees")


@app.route("/edit_employee/<int:eid>", methods=["GET"])
def edit_employee_page(eid):
    if not admin_only():
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM employees WHERE id=%s", (eid,))
    emp=c.fetchone()
    c.close()
    conn.close()

    if not emp:
        flash("Employee not found")
        return redirect("/admin/employees")
    return render_template("edit_employee.html", emp=emp)
@app.route("/update_employee/<int:eid>", methods=["POST"])
def update_employee(eid):

    if not admin_only():
        return redirect("/")

    name = request.form.get("name")
    mobile = request.form.get("mobile")
    email = request.form.get("email")
    address = request.form.get("address")
    photo_file = request.files.get("photo")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # get old photo
    c.execute("SELECT photo FROM employees WHERE id=%s", (eid,))
    emp = c.fetchone()

    photo_name = emp["photo"]

    # if new photo uploaded
    if photo_file and photo_file.filename:
        new_photo = save_photo(photo_file)

        if new_photo:
            remove_photo(photo_name)
            photo_name = new_photo

    # update employee
    c.execute("""
        UPDATE employees
        SET name=%s,
            mobile=%s,
            email=%s,
            address=%s,
            photo=%s
        WHERE id=%s
    """, (name, mobile, email, address, photo_name, eid))

    conn.commit()

    c.close()
    conn.close()

    flash("Employee updated successfully")
    return redirect("/admin/employees")


@app.route("/delete_employee/<int:eid>")
def delete_employee(eid):
    if not admin_only():
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT photo FROM employees WHERE id=%s", (eid,))
    emp=c.fetchone()
    if emp and emp["photo"]:
        remove_photo(emp["photo"])
    c.execute("DELETE FROM employees WHERE id=%s", (eid,))
    conn.commit()

    c.close()
    conn.close()

    flash("Employee deleted")
    return redirect("/admin/employees")


@app.route("/download_employees")
def download_employees():
    if not admin_only():
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM employees ORDER BY id")
    rows=c.fetchall()
    c.close()
    conn.close()

    return download_csv_from_rows(
        rows,
        ["id", "name", "mobile", "email", "address", "is_busy"],
        "employees.csv"
    )


# bookings admin
@app.route("/admin/bookings")
def admin_bookings():

    if not admin_only():
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("""
        SELECT b.*, u.name AS uname, cat.name AS category,
               e.name AS emp_name, e.mobile AS emp_mobile,
               e.email AS emp_email, e.address AS emp_address,
               e.photo AS emp_photo
        FROM bookings b
        LEFT JOIN customers u ON u.id=b.user_id
        LEFT JOIN categories cat ON cat.id=b.category_id
        LEFT JOIN employees e ON e.id=b.employee_id
        ORDER BY b.id DESC
    """)

    bookings = c.fetchall()

    # fetch clothes
    for b in bookings:

        c.execute("""
            SELECT bi.*, cl.cloth_name
            FROM booking_items bi
            JOIN clothes cl ON cl.id=bi.cloth_id
            WHERE bi.booking_id=%s
        """, (b["id"],))

        b["items"] = c.fetchall()

    c.execute(
        "SELECT * FROM employees WHERE is_busy=0 ORDER BY name"
    )
    employees = c.fetchall()

    c.close()
    conn.close()

    return render_template(
        "admin_bookings.html",
        bookings=bookings,
        employees=employees
    )

@app.route("/update_booking/<int:bid>", methods=["POST"])
def update_booking(bid):

    if not admin_only():
        return redirect("/")

    status = request.form.get("status", "Pending")
    emp = request.form.get("employee")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    # get booking
    c.execute("SELECT * FROM bookings WHERE id=%s", (bid,))
    booking = c.fetchone()

    if not booking:
        flash("Booking not found.")
        c.close()
        conn.close()
        return redirect("/admin/bookings")

    # block cancelled booking
    if booking["cancelled_flag"] == 1:
        flash("Cannot modify. This booking was cancelled by user.")
        c.close()
        conn.close()
        return redirect("/admin/bookings")

    # block completed booking
    if booking["status"] == "Completed":
        flash("Cannot modify. Task already completed.")
        c.close()
        conn.close()
        return redirect("/admin/bookings")

    # 🔴 NEW RULE
    if booking["employee_id"] is not None:
        flash("Employee already assigned. Cannot assign another employee.")
        c.close()
        conn.close()
        return redirect("/admin/bookings")

    # update booking
    c.execute("""
        UPDATE bookings
        SET status=%s, employee_id=%s
        WHERE id=%s
    """, (status, emp, bid))

    # mark employee busy
    if emp:
        c.execute("UPDATE employees SET is_busy=1 WHERE id=%s", (emp,))

    conn.commit()

    c.close()
    conn.close()

    flash("Booking updated successfully")
    return redirect("/admin/bookings")



@app.route("/download_bookings")
def download_bookings():
    if not admin_only():
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT * FROM bookings ORDER BY id")
    rows=c.fetchall()
    c.close()
    conn.close()


    return download_csv_from_rows(
        rows,
        ["id", "user_id", "category_id", "date", "status", "employee_id", "cancelled_flag"],
        "bookings.csv"
    )


@app.route("/export_users")
def export_users():
    if not admin_only():
        return redirect("/")
    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("SELECT id,email,role,login_time FROM users ORDER BY id DESC")
    rows=c.fetchall()
    c.close()
    conn.close()

    return download_csv_from_rows(rows, ["id", "email", "role", "login_time"], "users.csv")

@app.route("/admin/reports")
def admin_reports():

    if not admin_only():
        return redirect("/")

    return render_template("admin_reports.html")
@app.route("/report/users")
def report_users():

    if not admin_only():
        return redirect("/")

    conn=get_db()
    c=conn.cursor(dictionary=True)

    c.execute("SELECT * FROM users ORDER BY id DESC")
    rows=c.fetchall()

    c.close()
    conn.close()

    return render_template("report_users.html", rows=rows)
@app.route("/report/customers")
def report_customers():

    if not admin_only():
        return redirect("/")

    conn=get_db()
    c=conn.cursor(dictionary=True)

    c.execute("SELECT * FROM customers")
    rows=c.fetchall()

    c.close()
    conn.close()

    return render_template("report_customers.html", rows=rows)


@app.route("/report/employees")
def report_employees():

    if not admin_only():
        return redirect("/")

    conn=get_db()
    c=conn.cursor(dictionary=True)

    c.execute("SELECT * FROM employees")
    rows=c.fetchall()

    c.close()
    conn.close()

    return render_template("report_employees.html", rows=rows)      
@app.route("/report/services")
def report_services():

    if not admin_only():
        return redirect("/")

    conn=get_db()
    c=conn.cursor(dictionary=True)

    c.execute("SELECT * FROM categories")
    rows=c.fetchall()

    c.execute("SELECT * FROM clothes")
    clothes=c.fetchall()

    c.close()
    conn.close()

    return render_template("report_categories.html",
                           rows=rows,
                           clothes=clothes)

@app.route("/report/bookings")
def report_bookings():

    if not admin_only():
        return redirect("/")

    conn = get_db()
    c = conn.cursor(dictionary=True)

    c.execute("""
        SELECT b.*,
               u.name AS uname,
               cat.name AS category,
               e.name AS emp_name
        FROM bookings b
        LEFT JOIN customers u ON u.id = b.user_id
        LEFT JOIN categories cat ON cat.id = b.category_id
        LEFT JOIN employees e ON e.id = b.employee_id
        ORDER BY b.id DESC
    """)

    rows = c.fetchall()

    c.close()
    conn.close()

    return render_template("report_bookings.html", rows=rows)
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
