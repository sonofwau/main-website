from flask import Flask, request, jsonify, render_template
import os
import json # For pretty printing JSON in test functions
import sys # For command line arguments in test functions
from datetime import datetime

# --- Boggle App Imports ---
try:
    from boggle.board_search import board_search
    # Trie might not be directly used by flask_app anymore if board_search is self-contained
    # from boggle.board_search import Trie
    from boggle.def_lookup import def_lookup
    from boggle.def_format import format_definitions_html
except ImportError as e:
    print(f"Error importing Boggle modules: {e}")
    board_search = None
    def_lookup = None
    format_definitions_html = None

# --- MSL App Imports ---
try:
    from msl.msl_flask_app_blueprint import msl_blueprint, create_tables_if_not_exist_for_msl, get_db as get_msl_db
    # We need get_msl_db to call create_tables_if_not_exist_for_msl within app_context
except ImportError as e:
    print(f"Error importing MSL modules: {e}")
    msl_blueprint = None
    create_tables_if_not_exist_for_msl = None
    get_msl_db = None


app = Flask(__name__)

# --- App Configuration ---
# SECRET_KEY is crucial for session management (used by MSL app's login)
# For production, use a strong, fixed secret key (e.g., from an environment variable)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Boggle app configuration (board_search uses its internal default path)
TEST_BOARD = [
    ["O", "N", "C", "B", "T", "S"], ["V", "I", "Y", "O", "U", "R"],
    ["A", "M", "A", "R", "K", "I"], ["G", "E", "T", "I", "N", "G"],
    ["Y", "Th", "-", "S", "E", "T"], ["B", "O", "G", "G", "L", "E"]
]

# --- Register Blueprints ---
if msl_blueprint:
    app.register_blueprint(msl_blueprint, url_prefix='/msl')
    print("MSL Blueprint registered with /msl prefix.")
else:
    print("MSL Blueprint not loaded. MSL app functionality will be unavailable.")


# --- Database Initialization for MSL (Example using a CLI command) ---
# This is a more robust way to handle DB setup than calling it directly on startup.
# You would run this from your terminal: flask init-msl-db
@app.cli.command('init-msl-db')
def init_msl_db_command():
    """Initializes the MSL database and creates tables."""
    if create_tables_if_not_exist_for_msl and get_msl_db:
        try:
            with app.app_context(): # Create an application context
                # Test DB connection first
                db_conn = get_msl_db() # This should establish a connection or raise an error
                if db_conn:
                    print("MSL DB connection successful. Creating tables...")
                    create_tables_if_not_exist_for_msl()
                    print("MSL database tables checked/created.")
                else:
                    print("Failed to get MSL DB connection during init.")
        except Exception as e:
            print(f"An error occurred during MSL DB initialization: {e}")
            print("Please ensure your msl/msl_app_db_config.py is correct and MySQL server is running.")
    else:
        print("MSL table creation function or DB getter not available.")

# --- Boggle App Routes (and general app routes) ---
@app.route('/')
def home():
    # Provide links to both applications
    return """
    <h1>Welcome to JB's Glorious Work in Progress!</h1>
    <p><a href="/boggle">Go to Boggle App</a></p>
    <p><a href="/msl">Go to MSL Task Manager</a> (requires login)</p>
    """

@app.route('/boggle')
def boggle_page():
    return render_template('bogglePage.html') # Assumes templates/bogglePage.html

@app.route('/dict_search', methods=['POST'])
def handle_dict_search():
    if not board_search:
        return jsonify({"error": "Boggle dictionary search module not imported/initialized."}), 500
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    game_board = data.get('board')
    word_to_find = data.get('word')
    if not game_board: return jsonify({"error": "Missing 'board' in request"}), 400

    # board_search uses its own default path for condensedWordList.json
    results = board_search(game_board, word_to_find=word_to_find)

    try:
        # Ensure the log file path is robust, e.g., place it in an instance folder or configurable path
        # The instance_path is automatically created by Flask if it doesn't exist when app.instance_path is accessed.
        log_file_path = os.path.join(app.instance_path, "search_log.txt")
        os.makedirs(app.instance_path, exist_ok=True) # Ensure instance folder exists
        with open(log_file_path, 'a') as file:
            file.write(f'\n\n{datetime.now().strftime("%d-%b-%Y - %H:%M:%S")}\n') # Added Year for clarity
            file.writelines(f"Board received: {json.dumps(game_board, indent=2)}\n")
            file.writelines(f"Word to find: {word_to_find}\n")
            file.writelines(f"Results: {json.dumps(results, indent=2)}\n")
    except Exception as e:
        app.logger.error(f"Error writing to search_log.txt: {e}") # Use app logger for server-side logging

    if "Error" in results: return jsonify(results), 400
    if word_to_find and results.get("status") is False: return jsonify(results), 404
    return jsonify(results), 200

@app.route('/define_word', methods=['POST'])
def handle_define_word():
    if not def_lookup or not format_definitions_html:
        return jsonify({"error": "Definition lookup or formatting module not initialized."}), 500
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    word = data.get('word')
    if not word: return jsonify({"error": "Missing 'word' in request"}), 400
    raw_definition_data = def_lookup(word) # This function handles its own web requests
    if not raw_definition_data.get("status"):
        error_message = raw_definition_data.get("def", "Unknown error during definition lookup.")
        return jsonify({"status": False, "error": error_message}), 404
    try:
        processed_definition_data = format_definitions_html(raw_definition_data)
        html_output = processed_definition_data.get("def")
        if html_output: return jsonify({"status": True, "html_definition": html_output}), 200
        else: return jsonify({"status": False, "error": "Successfully fetched but failed to format definition."}), 500
    except Exception as e:
        app.logger.error(f"Error formatting definition for '{word}': {e}")
        return jsonify({"status": False, "error": f"An error occurred while formatting the definition: {str(e)}"}), 500

# --- Boggle Test Functions ---
def tb_search(word=None):
    # Ensure the app context is available for tests if they indirectly trigger DB operations
    # or things that rely on app context (like 'g').
    # For /dict_search, it doesn't directly use 'g' or app-context DB, but good practice.
    with app.app_context():
        with app.test_client() as client:
            payload = {"board": TEST_BOARD}
            if word: payload["word"] = word
            print(f"\n--- Testing /dict_search with board and word: '{word if word else 'all'}' ---")
            response = client.post('/dict_search', json=payload)
            print(f"Status Code: {response.status_code}")
            try: print("Response JSON:", json.dumps(response.get_json(), indent=2))
            except Exception as e: print(f"Could not parse JSON: {e}\nResponse Data: {response.data.decode()}")
            return response

def tb_define(word):
    if not word: print("Error: No word provided for tb_define."); return None
    with app.app_context(): # Good practice for test functions
        with app.test_client() as client:
            print(f"\n--- Testing /define_word for word: '{word}' ---")
            response = client.post('/define_word', json={"word": word})
            print(f"Status Code: {response.status_code}")
            try: print("Response JSON:", json.dumps(response.get_json(), indent=2))
            except Exception as e: print(f"Could not parse JSON: {e}\nResponse Data: {response.data.decode()}")
            return response

if __name__ == '__main__':
    # Check for command line arguments to run specific tests or the server
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "test_search":
            search_word = sys.argv[2] if len(sys.argv) > 2 else None
            tb_search(search_word)
        elif command == "test_define":
            if len(sys.argv) > 2: tb_define(sys.argv[2])
            else: print("Usage: python flask_app.py test_define <word>")
        elif command == "run_server":
            print("Starting Flask server on http://0.0.0.0:5000")
            print("Boggle app at http://0.0.0.0:5000/boggle")
            print("MSL app at http://0.0.0.0:5000/msl (after DB setup)")
            print("To initialize MSL DB (if not done): flask init-msl-db")
            app.run(debug=True, host='0.0.0.0', port=5000)
        else:
            print(f"Unknown command: {command}. Available: test_search [word], test_define <word>, run_server")
    else:
        # Default action: run the server if no command line arguments are given
        print("Starting Flask server by default on http://0.0.0.0:5000")
        print("Boggle app at http://0.0.0.0:5000/boggle")
        print("MSL app at http://0.0.0.0:5000/msl (after DB setup)")
        print("To initialize MSL DB (if not done): flask init-msl-db")
        app.run(debug=True, host='0.0.0.0', port=5000)
