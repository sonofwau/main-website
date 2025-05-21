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
from msl_app_db_config import DB_CONFIG

# --- Blueprint Definition ---
# All routes will be prefixed with '/msl_app' (or whatever you choose in the main app)
# If you want the API routes to be prefixed with /api, you can set url_prefix='/api' here,
# or you can nest blueprints, or set the prefix during registration in the main app.
# For simplicity, let's make the blueprint represent the whole "MSL App module"
# and the main app can decide the prefix. If no prefix is set during registration,
# the paths defined in routes below will be relative to the root.
#
# Let's assume you want to keep the /api prefix for API routes and others at root.
# We can make two blueprints or make the main app handle the non-API routes if they are simple.
# For this example, I'll create one blueprint for all routes that were in flask_app.py.
# The main app will register it, potentially with a prefix.

msl_blueprint = Blueprint('msl_app', __name__, template_folder='templates', static_folder='static')
# Note: If your templates/static folders for this blueprint are in a specific subdirectory
# related to this blueprint module, you might need to adjust template_folder path.
# If flask_app.py is in the root with templates/ and static/ folders, this should be fine.


# --- Database Helper Functions (associated with the app context via 'g') ---
def get_db():
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(**DB_CONFIG)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print(f"Database '{DB_CONFIG['database']}' does not exist.")
            else:
                print(f"MySQL Connection Error in get_db: {err}")
            raise # Re-raise the error
    return g.db

def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Register close_db to be called when the application context ends
# This will apply to the app that this blueprint is registered with.
@msl_blueprint.teardown_appcontext
def teardown_db_from_blueprint(exception):
    close_db(exception)


def query_db(query, args=None, one=False, commit=False, is_ddl=False):
    # ... (keep your existing query_db function, it uses get_db()) ...
    # Ensure it's defined here or imported if it was separate
    db_conn = get_db()
    # Using dictionary=True for SELECTs by default makes working with rows easier
    cursor = db_conn.cursor(dictionary=True if not (is_ddl or commit or one and not isinstance(query, str) and "INSERT" in query.upper()) else False)
    try:
        cursor.execute(query, args or ())
        if commit or is_ddl:
            db_conn.commit()
            return cursor.rowcount

        if one:
            result = cursor.fetchone()
            return result
        else:
            result = cursor.fetchall()
            return result
    except mysql.connector.Error as err:
        print(f"MySQL Error in query_db: {err}")
        print(f"Query: {query}")
        print(f"Args: {args}")
        db_conn.rollback()
        raise err
    finally:
        cursor.close()

def format_datetime_for_sql(dt_obj):
    if isinstance(dt_obj, str): return dt_obj
    if dt_obj == datetime.max: return "9999-12-31 23:59:59"
    if isinstance(dt_obj, datetime): return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
    return None

def new_id():
    return uuid.uuid4().hex[:8]

# --- Table Creation (call this from your main app setup) ---
def create_tables_if_not_exist_for_msl():
    # ... (keep your existing create_tables_if_not_exist function logic) ...
    # Make sure it uses query_db defined above
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
                Title VARCHAR(255), Due DATETIME, Date_Opened DATETIME, State INT,
                Date_Closed DATETIME, Creator_Username VARCHAR(80), Closor_Username VARCHAR(80),
                Summary TEXT, UI INT,
                FOREIGN KEY (Creator_Username) REFERENCES Users(username) ON DELETE SET NULL,
                FOREIGN KEY (Closor_Username) REFERENCES Users(username) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        "MSLEntry": """
            CREATE TABLE IF NOT EXISTS MSLEntry (
                EntryID VARCHAR(8) PRIMARY KEY, TaskID VARCHAR(8) NOT NULL, Date DATETIME,
                Text TEXT, Submitter_Username VARCHAR(80), Submitter_FullName VARCHAR(255),
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
            return redirect(url_for('msl_app.login', next=request.url)) # Note: endpoint name is 'blueprint_name.view_function_name'
        # Fetch user from DB to ensure they still exist and for g.user
        # This depends on how your main app handles user loading, or keep it simple:
        g.user = query_db("SELECT id, username, full_name FROM Users WHERE id = %s", (session['user_id'],), one=True)
        if not g.user:
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
    # ... (your existing get_tasks_logic function, ensure it uses query_db) ...
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
        if task_state == 0:
            time_val = f"---Completed: {task.get('Date_Closed', datetime.now()).strftime('%Y-%m-%d') if task.get('Date_Closed') else 'N/A'}---"
        elif isinstance(due_date, datetime):
            time_span = due_date - datetime.now()
            total_days_float = time_span.total_seconds() / (24 * 60 * 60)
            if total_days_float < 0: time_val = "---Overdue---"
            elif 0 <= total_days_float <= 1: time_val = "---Today---"
            elif 1 < total_days_float <= 7: time_val = "---This Week---"
            elif 7 < total_days_float <= 14: time_val = "---Next Week---"
        task["Filter_Date_Text"] = time_val
        for key, value in task.items():
            if isinstance(value, datetime): task[key] = value.isoformat()
        processed_tasks.append(task)

    if filter_property == "Filter_UI":
        custom_sort_order = ["---Urgent + Important---", "---Important + Not-Urgent---", "---Urgent + Not-Important---", "---Uncategorized---", "---Not-Urgent + Not-Important---"]
        processed_tasks.sort(key=lambda t: custom_sort_order.index(t["Filter_UI_Text"]) if t["Filter_UI_Text"] in custom_sort_order else len(custom_sort_order))
    elif filter_property == "Filter_Date":
        if task_state == 0:
            processed_tasks.sort(key=lambda t: t.get("Date_Closed") or '', reverse=True)
        else:
            custom_sort_order = ["---Overdue---", "---Today---", "---This Week---", "---Next Week---", "---Later---"]
            processed_tasks.sort(key=lambda t: custom_sort_order.index(t["Filter_Date_Text"]) if t["Filter_Date_Text"] in custom_sort_order else len(custom_sort_order))
    return processed_tasks


def get_msl_entries_logic(task_id):
    # ... (your existing get_msl_entries_logic function, ensure it uses query_db) ...
    entries = query_db("SELECT * FROM MSLEntry WHERE TaskID = %s ORDER BY Date", (task_id,))
    for entry in entries:
        for key, value in entry.items():
            if isinstance(value, datetime): entry[key] = value.isoformat()
    return entries

# --- Routes Registered on the Blueprint ---
# Note: url_for for redirects within the blueprint should use '.view_function_name'
# e.g., url_for('.login') if login is a view in this blueprint.
# If redirecting to an endpoint in another blueprint or the main app, use 'other_blueprint_name.view_function_name'

@msl_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # ... (your existing registration logic) ...
        # Ensure query_db is used correctly
        username = request.form['username']
        password = request.form['password']
        full_name = request.form['full_name']
        if not username or not password or not full_name: return "Missing fields", 400
        existing_user = query_db("SELECT id FROM Users WHERE username = %s", (username,), one=True)
        if existing_user: return "Username already exists", 400
        password_hash = pbkdf2_sha256.hash(password)
        try:
            query_db("INSERT INTO Users (username, password_hash, full_name) VALUES (%s, %s, %s)",
                     (username, password_hash, full_name), commit=True)
            return redirect(url_for('.login')) # Assuming login is in this blueprint
        except mysql.connector.Error as err:
            return f"Registration failed: {err}", 500
    return render_template('register.html') # Assumes templates/register.html exists

@msl_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # ... (your existing login logic) ...
        # Ensure query_db is used correctly
        username = request.form['username']
        password = request.form['password']
        user = query_db("SELECT id, username, password_hash, full_name FROM Users WHERE username = %s", (username,), one=True)
        if user and pbkdf2_sha256.verify(password, user['password_hash']):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            next_url = request.args.get('next') or url_for('.index') # Assuming index is in this blueprint
            return redirect(next_url)
        return "Invalid credentials", 401 # Or render_template with error
    return render_template('login.html') # Assumes templates/login.html exists

@msl_blueprint.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('.login')) # Assuming login is in this blueprint

@msl_blueprint.route('/')
@login_required
def index():
    # Ensure templates/index.html is found. If it's in a global templates folder,
    # the main app's template_folder setting will be used. If this blueprint
    # has its own 'templates' subfolder, set template_folder in Blueprint constructor.
    return render_template('index.html', username=get_current_user_username())

# --- API Endpoints (prefixed with /api by the main app if desired, or add url_prefix to blueprint) ---
# For API routes, it's common to have them under an /api prefix.
# If you want this blueprint to manage that, set url_prefix in the Blueprint definition:
# msl_blueprint = Blueprint('msl_app', __name__, url_prefix='/api', template_folder='templates')
# Then routes below would be, e.g. @msl_blueprint.route('/tasks') becomes accessible at /api/tasks

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
    # ... (your existing api_add_task logic) ...
    # Ensure query_db is used correctly
    data = request.json
    task_id = new_id()
    creator_username = get_current_user_username()
    due_date_str = data.get('Due')
    try:
        due_date = datetime.fromisoformat(due_date_str) if due_date_str else datetime.now() + timedelta(days=7)
    except ValueError: due_date = datetime.now() + timedelta(days=7)
    task_title = data.get('Title', 'New Task')
    task_summary = data.get('Summary', '')
    task_ui_raw = data.get('UI', 0)
    try: task_ui = int(task_ui_raw)
    except (ValueError, TypeError): task_ui = 0
    sql = """INSERT INTO Tasks (ID, Title, Due, Date_Opened, State, Date_Closed, Creator_Username, Summary, UI)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    args = (task_id, task_title, format_datetime_for_sql(due_date), format_datetime_for_sql(datetime.now()),
            1, None, creator_username, task_summary, task_ui)
    try:
        query_db(sql, args, commit=True)
        new_task_from_db = query_db("SELECT * FROM Tasks WHERE ID = %s", (task_id,), one=True)
        if new_task_from_db:
            for key in ['Due', 'Date_Opened', 'Date_Closed']:
                if new_task_from_db.get(key) and isinstance(new_task_from_db[key], datetime):
                    new_task_from_db[key] = new_task_from_db[key].isoformat()
            return jsonify(new_task_from_db), 201
        return jsonify({"error": "Task created but could not be retrieved"}), 500
    except Exception as e: return jsonify({"error": str(e)}), 500


@msl_blueprint.route('/api/task/<task_id>', methods=['PUT'])
@login_required
def api_update_task(task_id):
    # ... (your existing api_update_task logic) ...
    # Ensure query_db is used correctly
    data = request.json
    set_clauses = []; args = []
    allowed_fields = {"Title": "Title", "Summary": "Summary", "UI": "UI", "Due": "Due"}
    for field_key, db_column in allowed_fields.items():
        if field_key in data:
            value = data[field_key]
            if field_key == "UI": value = int(value)
            elif field_key == "Due":
                try: value = format_datetime_for_sql(datetime.fromisoformat(value) if value else None)
                except ValueError: return jsonify({"error": f"Invalid date format for Due: {data[field_key]}"}), 400
            set_clauses.append(f"{db_column} = %s"); args.append(value)
    if not set_clauses: return jsonify({"error": "No updateable fields provided"}), 400
    args.append(task_id)
    sql = f"UPDATE Tasks SET {', '.join(set_clauses)} WHERE ID = %s"
    try:
        query_db(sql, tuple(args), commit=True)
        updated_task = query_db("SELECT * FROM Tasks WHERE ID = %s", (task_id,), one=True)
        if updated_task:
            for key in ['Due', 'Date_Opened', 'Date_Closed']:
                if updated_task.get(key) and isinstance(updated_task[key], datetime):
                    updated_task[key] = updated_task[key].isoformat()
        return jsonify(updated_task)
    except Exception as e: return jsonify({"error": str(e)}), 500

@msl_blueprint.route('/api/task/<task_id>/complete', methods=['POST'])
@login_required
def api_complete_task(task_id):
    # ... (your existing api_complete_task logic) ...
    # Ensure query_db is used correctly
    closor_username = get_current_user_username()
    sql = "UPDATE Tasks SET State = 0, Closor_Username = %s, Date_Closed = %s WHERE ID = %s"
    args = (closor_username, format_datetime_for_sql(datetime.now()), task_id)
    try:
        query_db(sql, args, commit=True)
        return jsonify({"message": "Task completed"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500


@msl_blueprint.route('/api/msl_entries/<task_id>', methods=['GET'])
@login_required
def api_get_msl_entries(task_id):
    entries = get_msl_entries_logic(task_id)
    return jsonify(entries)

@msl_blueprint.route('/api/msl_entry', methods=['POST'])
@login_required
def api_add_msl_entry():
    # ... (your existing api_add_msl_entry logic) ...
    # Ensure query_db is used correctly
    data = request.json
    task_id = data.get('TaskID'); text_content = data.get('Text')
    if not task_id or not text_content: return jsonify({"error": "TaskID and Text are required"}), 400
    entry_id = new_id()
    submitter_username = get_current_user_username(); submitter_fullname = get_current_user_fullname()
    sql = """INSERT INTO MSLEntry (EntryID, TaskID, Date, Text, Submitter_Username, Submitter_FullName)
             VALUES (%s, %s, %s, %s, %s, %s)"""
    args = (entry_id, task_id, format_datetime_for_sql(datetime.now()), text_content, submitter_username, submitter_fullname)
    try:
        query_db(sql, args, commit=True)
        new_entry = query_db("SELECT * FROM MSLEntry WHERE EntryID = %s", (entry_id,), one=True)
        if new_entry and isinstance(new_entry.get('Date'), datetime): new_entry['Date'] = new_entry['Date'].isoformat()
        return jsonify(new_entry), 201
    except Exception as e: return jsonify({"error": str(e)}), 500


# --- To allow running this blueprint standalone for testing (optional) ---
if __name__ == '__main__':
    # This part is for testing this blueprint module directly.
    # Your main application will import 'msl_blueprint' and register it.
    app = Flask(__name__)
    app.secret_key = os.urandom(24) # Needs a secret key for sessions

    # Register the blueprint defined in this file
    # You can choose a URL prefix for all routes in this blueprint
    app.register_blueprint(msl_blueprint, url_prefix='/msl') # Example prefix

    # Important: The main app (or this test app) needs to set up the app context for DB,
    # and call create_tables if needed.
    # The @msl_blueprint.teardown_appcontext will handle closing DB for requests to this blueprint.

    print("Attempting to create MSL tables for standalone test run...")
    with app.app_context(): # Create an app context to use g and query_db
        # Create tables if they don't exist (using the function from this module)
        # Note: In a real main app, you'd call this more explicitly during app setup.
        try:
            # Ensure DB connection is possible before creating tables
            db_conn_test = get_db()
            if db_conn_test:
                create_tables_if_not_exist_for_msl()
        except Exception as e:
            print(f"Error during standalone table creation or DB connection: {e}")


    print("\nMSL Blueprint standalone test app running.")
    print(f"Access MSL app at http://127.0.0.1:5005/msl (or /msl/api/tasks etc.)")
    print(f"For example, login at http://127.0.0.1:5005/msl/login")
    app.run(debug=True, port=5005)