# flask_app.py (now defines a Blueprint)

from flask import Blueprint, Flask, g, jsonify, redirect, render_template, request, session, url_for
import mysql.connector
from mysql.connector import errorcode # Make sure this is imported if used in get_db
import os
import uuid
from datetime import datetime, timedelta
from functools import wraps
from passlib.hash import pbkdf2_sha256

# Import DB_CONFIG from your configuration file
# ***** CORRECTED IMPORT HERE *****
from .msl_app_db_config import DB_CONFIG # Use relative import for blueprint

# --- Blueprint Definition ---
msl_blueprint = Blueprint('msl_app', __name__,
                          template_folder='templates', # Relative to 'msl' folder
                          static_folder='static')     # Relative to 'msl' folder


# --- Database Helper Functions (associated with the app context via 'g') ---
def get_db():
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(**DB_CONFIG)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("MSL DB Error: Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print(f"MSL DB Error: Database '{DB_CONFIG.get('database', 'N/A')}' does not exist.")
            else:
                print(f"MSL DB Error: MySQL Connection Error in get_db: {err}")
            raise # Re-raise the error
    return g.db

def close_db(exception=None): # The exception parameter is passed by teardown_request
    db = g.pop('db', None)
    if db is not None:
        db.close()
        # print("MSL DB connection closed.") # Optional: for debugging

# Register close_db to be called when the request context ends for this blueprint
@msl_blueprint.teardown_request
def teardown_db_from_blueprint(exception): # Renamed for clarity, matches teardown_request signature
    close_db(exception)


def query_db(query, args=None, one=False, commit=False, is_ddl=False):
    db_conn = get_db()
    # Using dictionary=True for SELECTs by default makes working with rows easier
    cursor = db_conn.cursor(dictionary=True) # Always use dictionary=True for simplicity with row access
    
    try:
        cursor.execute(query, args or ())
        if commit or is_ddl:
            db_conn.commit()
            return cursor.rowcount # Useful for INSERT/UPDATE/DELETE/DDL

        # For SELECT queries
        if one:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
        return result
    except mysql.connector.Error as err:
        print(f"MySQL Error in query_db: {err}")
        # cursor.statement shows the query after Python's %s substitution (if any by the driver)
        # For mysql.connector, it's better to log the raw query and args.
        print(f"Raw Query Attempted: {query}")
        print(f"Arguments: {args}")
        db_conn.rollback() # Rollback on error for transactional integrity
        raise err # Re-raise to be handled by the route or a global error handler
    finally:
        cursor.close()

def format_datetime_for_sql(dt_obj):
    if isinstance(dt_obj, str): return dt_obj # Allow pre-formatted strings
    if dt_obj == datetime.max: return "9999-12-31 23:59:59"
    if isinstance(dt_obj, datetime): return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    return None

def new_id():
    return uuid.uuid4().hex[:8]

# --- Table Creation (call this from your main app setup) ---
def create_tables_if_not_exist_for_msl():
    # DDL statements for creating tables if they don't exist
    tables = {
        "Users": """
            CREATE TABLE IF NOT EXISTS Users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        "Tasks": """
            CREATE TABLE IF NOT EXISTS Tasks (
                ID VARCHAR(8) PRIMARY KEY,
                Title VARCHAR(255), 
                Due DATETIME, 
                Date_Opened DATETIME, 
                State INT,
                Date_Closed DATETIME, 
                Creator_Username VARCHAR(80), 
                Closor_Username VARCHAR(80),
                Summary TEXT, 
                UI INT,
                FOREIGN KEY (Creator_Username) REFERENCES Users(username) ON DELETE SET NULL,
                FOREIGN KEY (Closor_Username) REFERENCES Users(username) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        "MSLEntry": """
            CREATE TABLE IF NOT EXISTS MSLEntry (
                EntryID VARCHAR(8) PRIMARY KEY, 
                TaskID VARCHAR(8) NOT NULL, 
                Date DATETIME,
                Text TEXT, 
                Submitter_Username VARCHAR(80), 
                Submitter_FullName VARCHAR(255),
                FOREIGN KEY (TaskID) REFERENCES Tasks(ID) ON DELETE CASCADE,
                FOREIGN KEY (Submitter_Username) REFERENCES Users(username) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    }
    for table_name, ddl_query in tables.items():
        try:
            print(f"MSL Blueprint: Creating table {table_name} if not exists...")
            query_db(ddl_query, is_ddl=True) # query_db handles commit for DDL
            print(f"MSL Blueprint: Table {table_name} checked/created.")
        except mysql.connector.Error as err:
            print(f"MSL Blueprint: Error creating table {table_name}: {err}")


# --- Authentication Helpers (associated with the blueprint's app context) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('msl_app.login', next=request.url))
        
        # Fetch user from DB to ensure they still exist and for g.user
        g.user = query_db("SELECT id, username, full_name FROM Users WHERE id = %s", (session['user_id'],), one=True)
        if not g.user: # User deleted or session invalid
            session.clear()
            return redirect(url_for('msl_app.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_username():
    return session.get('username')

def get_current_user_fullname():
    return session.get('full_name')

# --- Logic Functions (used by blueprint routes) ---
def get_tasks_logic(creator_username, task_state=1, filter_property="Filter_UI"):
    sql_query = "SELECT * FROM Tasks WHERE State = %s AND Creator_Username = %s"
    args = (task_state, creator_username,)
    tasks_from_db = query_db(sql_query, args)
    
    processed_tasks = []
    for task in tasks_from_db:
        ui_val = task.get("UI")
        if ui_val == 1: task["Filter_UI_Text"] = "---Urgent + Important---"
        elif ui_val == 2: task["Filter_UI_Text"] = "---Important + Not-Urgent---"
        elif ui_val == 3: task["Filter_UI_Text"] = "---Urgent + Not-Important---"
        elif ui_val == 4: task["Filter_UI_Text"] = "---Not-Urgent + Not-Important---"
        else: task["Filter_UI_Text"] = "---Uncategorized---"

        due_date = task.get("Due")
        time_val = "---Later---"
        if task_state == 0: # Completed tasks
            closed_date_obj = task.get('Date_Closed')
            time_val = f"---Completed: {closed_date_obj.strftime('%Y-%m-%d') if isinstance(closed_date_obj, datetime) else 'N/A'}---"
        elif isinstance(due_date, datetime):
            time_span = due_date - datetime.now()
            total_days_float = time_span.total_seconds() / (24 * 60 * 60)
            if total_days_float < 0: time_val = "---Overdue---"
            elif 0 <= total_days_float <= 1: time_val = "---Today---"
            elif 1 < total_days_float <= 7: time_val = "---This Week---"
            elif 7 < total_days_float <= 14: time_val = "---Next Week---"
        task["Filter_Date_Text"] = time_val
        
        # Convert all datetime objects to ISO format strings for JSON serialization
        for key, value in task.items():
            if isinstance(value, datetime): 
                task[key] = value.isoformat()
        processed_tasks.append(task)

    # Sorting logic
    if filter_property == "Filter_UI":
        custom_sort_order = ["---Urgent + Important---", "---Important + Not-Urgent---", "---Urgent + Not-Important---", "---Uncategorized---", "---Not-Urgent + Not-Important---"]
        processed_tasks.sort(key=lambda t: custom_sort_order.index(t["Filter_UI_Text"]) if t["Filter_UI_Text"] in custom_sort_order else len(custom_sort_order))
    elif filter_property == "Filter_Date":
        if task_state == 0: # For completed tasks, sort by Date_Closed descending
            processed_tasks.sort(key=lambda t: t.get("Date_Closed") or '', reverse=True)
        else: # For active tasks
            custom_sort_order = ["---Overdue---", "---Today---", "---This Week---", "---Next Week---", "---Later---"]
            processed_tasks.sort(key=lambda t: custom_sort_order.index(t["Filter_Date_Text"]) if t["Filter_Date_Text"] in custom_sort_order else len(custom_sort_order))
    return processed_tasks


def get_msl_entries_logic(task_id):
    entries = query_db("SELECT * FROM MSLEntry WHERE TaskID = %s ORDER BY Date", (task_id,))
    for entry in entries:
        for key, value in entry.items(): # Ensure all datetimes are ISO strings
            if isinstance(value, datetime): 
                entry[key] = value.isoformat()
    return entries

# --- Routes Registered on the Blueprint ---
@msl_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']

        if not username or not password or not full_name:
            # Consider flashing a message or rendering template with error
            return "Missing fields", 400 

        existing_user = query_db("SELECT id FROM Users WHERE username = %s", (username,), one=True)
        if existing_user:
            # Consider flashing a message
            return "Username already exists", 400

        password_hash = pbkdf2_sha256.hash(password)
        try:
            query_db("INSERT INTO Users (username, password_hash, full_name) VALUES (%s, %s, %s)",
                     (username, password_hash, full_name), commit=True)
            # Consider flashing a success message
            return redirect(url_for('.login')) # '.login' refers to login view in this blueprint
        except mysql.connector.Error as err:
            # Log the error
            print(f"Error during registration: {err}")
            return f"Registration failed. Please try again later.", 500
    return render_template('msl_register.html') # Assumes msl/templates/msl_register.html

@msl_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db("SELECT id, username, password_hash, full_name FROM Users WHERE username = %s", (username,), one=True)
        
        if user and pbkdf2_sha256.verify(password, user['password_hash']):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            next_url = request.args.get('next') or url_for('.index') # '.index' for this blueprint
            return redirect(next_url)
        # Consider flashing a message for invalid credentials
        return "Invalid credentials", 401 # Or render_template with error
    return render_template('msl_login.html') # Assumes msl/templates/msl_login.html

@msl_blueprint.route('/logout')
@login_required # Ensures user is logged in to log out
def logout():
    session.clear()
    # Consider flashing a "Logged out successfully" message
    return redirect(url_for('.login'))

@msl_blueprint.route('/') # This will be /msl/ if blueprint prefix is /msl
@login_required
def index():
    # Pass current user's username to the template
    return render_template('msl_index.html', username=get_current_user_username())

# --- API Endpoints ---
# These will be prefixed, e.g., /msl/api/tasks if blueprint prefix is /msl

@msl_blueprint.route('/api/tasks', methods=['GET'])
@login_required
def api_get_tasks():
    filter_prop = request.args.get('filter_by', 'Filter_UI')
    current_username = get_current_user_username()
    tasks = get_tasks_logic(creator_username=current_username, task_state=1, filter_property=filter_prop)
    return jsonify(tasks)

@msl_blueprint.route('/api/tasks/completed', methods=['GET'])
@login_required
def api_get_completed_tasks():
    filter_prop = request.args.get('filter_by', 'Filter_UI')
    current_username = get_current_user_username()
    tasks = get_tasks_logic(creator_username=current_username, task_state=0, filter_property=filter_prop)
    return jsonify(tasks)

@msl_blueprint.route('/api/task', methods=['POST'])
@login_required
def api_add_task():
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400

    task_id = new_id()
    creator_username = get_current_user_username()
    
    due_date_str = data.get('Due')
    try:
        # Handle empty string for due_date or invalid format
        due_date = datetime.fromisoformat(due_date_str) if due_date_str else datetime.now() + timedelta(days=7)
    except ValueError:
        due_date = datetime.now() + timedelta(days=7) # Default if format is bad

    task_title = data.get('Title', 'New Task').strip()
    if not task_title: return jsonify({"error": "Task title cannot be empty"}), 400

    task_summary = data.get('Summary', '')
    task_ui_raw = data.get('UI', 0)
    try: 
        task_ui = int(task_ui_raw)
    except (ValueError, TypeError): 
        task_ui = 0 # Default UI if conversion fails
    
    sql = """INSERT INTO Tasks (ID, Title, Due, Date_Opened, State, Date_Closed, Creator_Username, Summary, UI)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    args = (task_id, task_title, format_datetime_for_sql(due_date), format_datetime_for_sql(datetime.now()),
            1, None, creator_username, task_summary, task_ui)
    try:
        query_db(sql, args, commit=True)
        new_task_from_db = query_db("SELECT * FROM Tasks WHERE ID = %s", (task_id,), one=True)
        if new_task_from_db:
            # Ensure datetimes are ISO strings for JSON
            for key in ['Due', 'Date_Opened', 'Date_Closed']:
                if new_task_from_db.get(key) and isinstance(new_task_from_db[key], datetime):
                    new_task_from_db[key] = new_task_from_db[key].isoformat()
            return jsonify(new_task_from_db), 201
        return jsonify({"error": "Task created but could not be retrieved"}), 500
    except Exception as e: 
        print(f"Error in api_add_task: {e}") # Log error
        return jsonify({"error": "Failed to add task due to a server error."}), 500


@msl_blueprint.route('/api/task/<task_id>', methods=['PUT'])
@login_required
def api_update_task(task_id):
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400

    set_clauses = []
    args = []
    allowed_fields = {"Title": "Title", "Summary": "Summary", "UI": "UI", "Due": "Due"}

    for field_key, db_column in allowed_fields.items():
        if field_key in data: # Check if key exists in payload
            value = data[field_key]
            if field_key == "Title":
                value = value.strip()
                if not value: return jsonify({"error": "Task title cannot be empty"}), 400
            if field_key == "UI": 
                try: value = int(value)
                except (ValueError, TypeError): return jsonify({"error": f"Invalid value for UI: {data[field_key]}"}), 400
            elif field_key == "Due":
                if value: # If Due is provided and not empty
                    try: value = format_datetime_for_sql(datetime.fromisoformat(value))
                    except ValueError: return jsonify({"error": f"Invalid date format for Due: {data[field_key]}"}), 400
                else: # If Due is empty string or null, set it to NULL in DB
                    value = None 
            set_clauses.append(f"{db_column} = %s")
            args.append(value)
    
    if not set_clauses: 
        return jsonify({"error": "No updateable fields provided"}), 400
    
    args.append(task_id) # For WHERE ID = %s
    sql = f"UPDATE Tasks SET {', '.join(set_clauses)} WHERE ID = %s"
    
    try:
        query_db(sql, tuple(args), commit=True)
        updated_task = query_db("SELECT * FROM Tasks WHERE ID = %s", (task_id,), one=True)
        if updated_task:
            for key in ['Due', 'Date_Opened', 'Date_Closed']:
                if updated_task.get(key) and isinstance(updated_task[key], datetime):
                    updated_task[key] = updated_task[key].isoformat()
            return jsonify(updated_task)
        return jsonify({"error": "Task not found after update"}), 404
    except Exception as e: 
        print(f"Error in api_update_task: {e}") # Log error
        return jsonify({"error": "Failed to update task due to a server error."}), 500

@msl_blueprint.route('/api/task/<task_id>/complete', methods=['POST'])
@login_required
def api_complete_task(task_id):
    closor_username = get_current_user_username()
    sql = "UPDATE Tasks SET State = 0, Closor_Username = %s, Date_Closed = %s WHERE ID = %s"
    args = (closor_username, format_datetime_for_sql(datetime.now()), task_id)
    try:
        query_db(sql, args, commit=True)
        return jsonify({"message": "Task completed"}), 200
    except Exception as e: 
        print(f"Error in api_complete_task: {e}") # Log error
        return jsonify({"error": "Failed to complete task due to a server error."}), 500


@msl_blueprint.route('/api/msl_entries/<task_id>', methods=['GET'])
@login_required
def api_get_msl_entries(task_id):
    entries = get_msl_entries_logic(task_id)
    return jsonify(entries)

@msl_blueprint.route('/api/msl_entry', methods=['POST'])
@login_required
def api_add_msl_entry():
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400

    task_id = data.get('TaskID')
    text_content = data.get('Text')
    
    if not task_id or not text_content or not text_content.strip(): 
        return jsonify({"error": "TaskID and non-empty Text are required"}), 400
    
    entry_id = new_id()
    submitter_username = get_current_user_username()
    submitter_fullname = get_current_user_fullname()
    
    sql = """INSERT INTO MSLEntry (EntryID, TaskID, Date, Text, Submitter_Username, Submitter_FullName)
             VALUES (%s, %s, %s, %s, %s, %s)"""
    args = (entry_id, task_id, format_datetime_for_sql(datetime.now()), text_content.strip(), submitter_username, submitter_fullname)
    
    try:
        query_db(sql, args, commit=True)
        new_entry = query_db("SELECT * FROM MSLEntry WHERE EntryID = %s", (entry_id,), one=True)
        if new_entry:
            if isinstance(new_entry.get('Date'), datetime): # Ensure datetime is ISO string
                new_entry['Date'] = new_entry['Date'].isoformat()
            return jsonify(new_entry), 201
        return jsonify({"error": "Entry created but could not be retrieved"}), 500
    except Exception as e: 
        print(f"Error in api_add_msl_entry: {e}") # Log error
        return jsonify({"error": "Failed to add MSL entry due to a server error."}), 500


# --- To allow running this blueprint standalone for testing (optional) ---
if __name__ == '__main__':
    # This part is for testing this blueprint module directly.
    # Your main application will import 'msl_blueprint' and register it.
    app_test = Flask(__name__) # Create a new Flask app instance for testing
    app_test.secret_key = os.urandom(24) # Needs a secret key for sessions

    # Register the blueprint defined in this file
    app_test.register_blueprint(msl_blueprint, url_prefix='/msl_standalone')

    print("Attempting to create MSL tables for standalone test run...")
    with app_test.app_context(): # Use the test app's context
        try:
            db_conn_test = get_db() # This will use g from app_test.app_context()
            if db_conn_test:
                create_tables_if_not_exist_for_msl()
        except Exception as e:
            print(f"Error during standalone table creation or DB connection: {e}")

    print("\nMSL Blueprint standalone test app running.")
    print(f"Access MSL app at http://127.0.0.1:5005/msl_standalone")
    app_test.run(debug=True, port=5005)
