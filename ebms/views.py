from django.shortcuts import render, redirect
from django.contrib import messages
from .db_utils import get_connection
from django.utils.timezone import now
from decimal import Decimal
from .db_utils import get_connection

# 🌍 Global context variables
current_user = {
    "username": None,
    "is_admin": False
}

def home(request):
    return render(request, 'home.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST['email']
        name = request.POST['name']
        account_number = request.POST['account_number']
        address = request.POST['address']

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_requests (username, password, email, name, account_number, address, request_type)
            VALUES (%s, %s, %s, %s, %s, %s, 'register')
        """, (username, password, email, name, account_number, address))
        conn.commit()
        conn.close()

        return render(request, 'register.html', {
            'message': 'Registration submitted. Waiting for admin approval.'
        })
    return render(request, 'register.html')



def login_view(request):
    global current_user

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            current_user["username"] = user[1]
            current_user["is_admin"] = bool(user[4])
            return redirect('admin_dashboard' if current_user["is_admin"] else 'customer_dashboard')
        else:
            messages.error(request, "Invalid login.")
    
    return render(request, 'login.html')


def logout_view(request):
    global current_user
    current_user["username"] = None
    current_user["is_admin"] = False
    return render(request, 'logout.html')


def get_column_names(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return [row[0] for row in cursor.fetchall()]



def admin_dashboard(request):
    global current_user
    if not current_user["is_admin"]:
        return redirect('login')

    conn = get_connection()
    cur = conn.cursor()

    tables = ['users', 'customers', 'bills', 'billing_rates', 'electricity_usage', 'payments']
    data = {}

    for table in tables:
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        columns = [col[0] for col in cur.description]  # ✅ Capture column names
        data[table] = {
            "columns": columns,
            "rows": rows
        }

    # Fetch user requests
    cur.execute("SELECT * FROM user_requests WHERE admin_action_taken = 1 ORDER BY timestamp DESC")
    requests = cur.fetchall()

    conn.close()
    return render(request, 'admin_dashboard.html', {'data': data, 'requests': requests})






def approve_registration(request, request_id):
    global current_user
    if not current_user["is_admin"]:
        return redirect('login')

    conn = get_connection()
    cur = conn.cursor()

    # Fetch from user_requests
    cur.execute("SELECT * FROM user_requests WHERE id=%s AND request_type='register'", (request_id,))
    req = cur.fetchone()

    if req:
        username, password, email, name, account_number, address = req[1], req[2], req[3], req[4], req[5], req[6]

        # Insert into users and customers
        cur.execute("INSERT INTO users (username, password, email) VALUES (%s, %s, %s)", (username, password, email))
        cur.execute("INSERT INTO customers (username, account_number, name, address) VALUES (%s, %s, %s, %s)", (username, account_number, name, address))

        # Mark request as processed
        cur.execute("UPDATE user_requests SET admin_action_taken = 0 WHERE id = %s", (request_id,))
        conn.commit()

    conn.close()
    return redirect("admin_dashboard")


def approve_delete(request, username):
    global current_user
    if not current_user["is_admin"]:
        return redirect('login')

    conn = get_connection()
    cur = conn.cursor()

    # Delete user and related data
    cur.execute("DELETE FROM users WHERE username=%s", (username,))
    cur.execute("DELETE FROM customers WHERE username=%s", (username,))
    cur.execute("DELETE FROM bills WHERE username=%s", (username,))
    cur.execute("DELETE FROM electricity_usage WHERE username=%s", (username,))
    cur.execute("DELETE FROM payments WHERE username=%s", (username,))

    # Optional: mark any delete request as resolved
    cur.execute("INSERT INTO user_requests (username, request_type, admin_action_taken) VALUES (%s, 'delete', 0)", (username,))

    conn.commit()
    conn.close()
    return redirect("admin_dashboard")


def reject_request(request, request_id):
    global current_user
    if not current_user["is_admin"]:
        return redirect("login")

    if request.method == "POST":
        reason = request.POST.get("reason")
        req_type = request.POST.get("type")

        conn = get_connection()
        cur = conn.cursor()

        # Set reason and mark as resolved
        cur.execute("""
            UPDATE user_requests 
            SET rejection_reason=%s, admin_action_taken=0, delete_requested=0 
            WHERE id=%s AND request_type=%s
        """, (reason, request_id, req_type))

        conn.commit()
        conn.close()

    return redirect("admin_dashboard")


def update_tables(request):
    global current_user
    if not current_user["is_admin"]:
        return redirect('login')

    if request.method == "POST":
        conn = get_connection()
        cur = conn.cursor()

        # Extract and group data
        from collections import defaultdict
        updates = defaultdict(lambda: defaultdict(list))

        for key, value in request.POST.items():
            if key == 'csrfmiddlewaretoken': continue
            try:
                table, row_index, col_index = key.split('_')
                updates[table][row_index].append((int(col_index), value))
            except:
                continue

        for table, rows in updates.items():
            for row_index, cols in rows.items():
                # Sort by column index
                cols.sort()
                values = [val for _, val in cols]
                columns = ', '.join([f'`{col}`' for col in get_column_names(cur, table)])

                # Assuming first column is primary key (update by first field)
                set_clause = ', '.join([f"`{col}`=%s" for col in get_column_names(cur, table)[1:]])
                cur.execute(f"UPDATE {table} SET {set_clause} WHERE {get_column_names(cur, table)[0]} = %s",
                            values[1:] + [values[0]])

        conn.commit()
        conn.close()
    return redirect("admin_dashboard")


def customer_dashboard(request):
    global current_user
    if not current_user["username"]:
        return redirect('login')

    username = current_user["username"]
    conn = get_connection()
    cur = conn.cursor()

    data = {}
    queries = {
        'customers': "SELECT * FROM customers WHERE username=%s",
        'bills': "SELECT * FROM bills WHERE username=%s",
        'billing_rates': "SELECT * FROM billing_rates",  # no %s
        'electricity_usage': "SELECT * FROM electricity_usage WHERE username=%s",
        'payments': "SELECT * FROM payments WHERE username=%s"
    }

    for table, q in queries.items():
        if '%s' in q:
            cur.execute(q, (username,))
        else:
            cur.execute(q)
        data[table] = cur.fetchall()

    conn.close()
    print(data)
    return render(request, 'customer_dashboard.html', {'data': data, 'user': username})


def bill_generation(request):
    from .db_utils import get_connection  # in case not already imported
    global current_user

    if not current_user["username"]:
        return redirect("login")  # fallback protection

    username = current_user["username"]

    conn = get_connection()
    with conn.cursor() as cur:
        # Fetch customer details
        cur.execute("""
            SELECT account_number, name, address
            FROM customers
            WHERE username=%s
        """, [username])
        customer = cur.fetchone()
        if not customer:
            conn.close()
            return render(request, 'bill_generation.html', {'error': 'Customer record not found.'})
        account_number, name, address = customer

        # Fetch user email
        cur.execute("SELECT email FROM users WHERE username=%s", [username])
        email_row = cur.fetchone()
        email = email_row[0] if email_row else "N/A"

        # Get latest bill
        cur.execute("""
            SELECT id, month, total_amount_due, payment_status
            FROM bills
            WHERE username=%s
            ORDER BY month DESC
            LIMIT 1
        """, [username])
        bill = cur.fetchone()
        if not bill:
            conn.close()
            return render(request, 'bill_generation.html', {'error': 'No bills found.'})
        bill_id, bill_month, total_due, payment_status = bill

        # Get meter reading for that month
        cur.execute("""
            SELECT meter_reading
            FROM electricity_usage
            WHERE username=%s AND month=%s
        """, [username, bill_month])
        usage_row = cur.fetchone()
        meter_reading = usage_row[0] if usage_row else "N/A"

        # Get payment details
        cur.execute("""
            SELECT payment_date, amount_paid
            FROM payments
            WHERE bill_id=%s
        """, [bill_id])
        payment_row = cur.fetchone()
        payment_date = payment_row[0] if payment_row else None
        amount_paid = payment_row[1] if payment_row else None

    conn.close()

    context = {
        "account_number": account_number,
        "name": name,
        "address": address,
        "email": email,
        "bill_month": bill_month,
        "total_due": total_due,
        "payment_status": payment_status,
        "meter_reading": meter_reading,
        "payment_date": payment_date,
        "amount_paid": amount_paid,
    }

    print(context)  # Debugging output
    return render(request, "bill_generation.html", context)




                              


def request_delete(request):
    global current_user
    if not current_user["username"]:
        return redirect("login")

    username = current_user["username"]

    conn = get_connection()
    cur = conn.cursor()

    # Prevent duplicate delete request
    cur.execute("""
        SELECT COUNT(*) FROM user_requests 
        WHERE username = %s AND request_type = 'delete' 
        AND delete_requested = 1 AND admin_action_taken = 1
    """, (username,))
    already_requested = cur.fetchone()[0]

    if not already_requested:
        # Fetch details from users and customers table
        cur.execute("SELECT password, email FROM users WHERE username = %s", (username,))
        user_data = cur.fetchone()

        cur.execute("SELECT name, account_number, address FROM customers WHERE username = %s", (username,))
        customer_data = cur.fetchone()

        if user_data and customer_data:
            password, email = user_data
            name, account_number, address = customer_data

            # Insert full detail delete request
            cur.execute("""
                INSERT INTO user_requests (
                    username, password, email, name, account_number, address, 
                    request_type, delete_requested, admin_action_taken
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'delete', 1, 1)
            """, (username, password, email, name, account_number, address))

            conn.commit()
            messages.success(request, "Your account deletion request has been submitted to Admin.")
        else:
            messages.error(request, "Could not retrieve user details for deletion request.")
    else:
        messages.warning(request, "You have already requested account deletion.")

    conn.close()
    return redirect("customer_dashboard")





def update_profile(request):
    if request.method == 'POST':
        customer_id = request.POST.get('id')
        name = request.POST.get('name')
        address = request.POST.get('address')

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE customers SET name=%s, address=%s WHERE id=%s", (name, address, customer_id))
        conn.commit()
        conn.close()

        return redirect('customer_dashboard')



def delete_user(request, username):
    global current_user
    if not current_user["is_admin"]:
        return redirect("login")

    conn = get_connection()
    cur = conn.cursor()

    # Delete child records first
    cur.execute("DELETE FROM payments WHERE username=%s", (username,))
    cur.execute("DELETE FROM electricity_usage WHERE username=%s", (username,))
    cur.execute("DELETE FROM bills WHERE username=%s", (username,))
    cur.execute("DELETE FROM customers WHERE username=%s", (username,))

    # Finally delete parent record
    cur.execute("DELETE FROM users WHERE username=%s", (username,))

    conn.commit()
    conn.close()

    return redirect("admin_dashboard")
