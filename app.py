from flask import Flask, render_template, request, jsonify, send_from_directory
import openai
import os
import sys
import json
import webbrowser
from threading import Timer
import subprocess
from datetime import datetime

app = Flask(
    __name__,
    static_folder=".",  # Serve static files from the current directory
    template_folder="."  # Serve templates from the current directory
)

# Function to resolve paths for bundled files (PyInstaller compatibility)
def resource_path(relative_path):
    """Get the absolute path to a resource."""
    if hasattr(sys, '_MEIPASS'):  # Check if running as a PyInstaller executable
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Load coding problems from the JSON file
with open(resource_path('problems.json')) as f:
    problems = json.load(f)

# OpenAI API key
openai.api_key = '' 

# Log directories
BASE_DIR = os.path.join(os.path.abspath("."), 'logs')
CLIPBOARD_DIR = os.path.join(BASE_DIR, 'clipboard')
USER_PROGRESS_DIR = os.path.join(BASE_DIR, 'user_progress')
CHAT_LOGS_DIR = os.path.join(BASE_DIR, 'chat_logs')

# Ensure log directories exist
os.makedirs(CLIPBOARD_DIR, exist_ok=True)
os.makedirs(USER_PROGRESS_DIR, exist_ok=True)
os.makedirs(CHAT_LOGS_DIR, exist_ok=True)

# Temporary directory for Java files
TEMP_DIR = os.path.join(os.getcwd(), "temp")
#added now idk if works
if hasattr(sys, '_MEIPASS'):
    # Use a temp directory specific to the PyInstaller runtime
    TEMP_DIR = os.path.join(sys._MEIPASS, "temp")
#end
os.makedirs(TEMP_DIR, exist_ok=True)
# Paths for bundled JRE
JAVA_DIR = os.path.join(os.getcwd(), "jre", "bin")
JAVAC = os.path.join(JAVA_DIR, "javac")
JAVA = os.path.join(JAVA_DIR, "java")


@app.route('/')
def index():
    """Render the main IDE page."""
    return render_template('index.html', problems=problems)


@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files directly."""
    return send_from_directory('.', filename)




@app.route('/run_code', methods=['POST'])
def run_code():
    """Run Java code submitted by the user."""
    code = request.json.get('code', '')
    problem_id = request.json.get('problem_id')
    problem = next((p for p in problems if p["id"] == problem_id), None)

    if not problem:
        return jsonify({"result": [], "correct": False, "message": "Invalid problem ID"})

    test_cases = problem.get("test_cases", [])
    java_file = os.path.join(TEMP_DIR, "Main.java")

    # Save the Java code to a file
    with open(java_file, "w") as f:
        f.write(code)

    try:
        # Determine the path to the JRE
        java_path = os.path.join(sys._MEIPASS, "jre", "bin", "java")
        javac_path = os.path.join(sys._MEIPASS, "jre", "bin", "javac")

        # Compile the Java code
        compile_process = subprocess.run(
            [javac_path, java_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if compile_process.returncode != 0:
            return jsonify({
                "result": [],
                "correct": False,
                "message": f"Compilation error: {compile_process.stderr.decode()}"
            })

        # Run test cases
        results = []
        all_correct = True

        for case in test_cases:
            args = case["args"]
            expected_output = case["expected_output"]

            run_process = subprocess.run(
                [java_path, "-cp", TEMP_DIR, "Main"] + [str(arg) for arg in args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if run_process.returncode != 0:
                return jsonify({
                    "result": [],
                    "correct": False,
                    "message": f"Runtime error: {run_process.stderr.decode()}"
                })

            user_output = run_process.stdout.decode().strip()
            is_correct = user_output == expected_output
            all_correct = all_correct and is_correct

            results.append({
                "args": args,
                "expected_output": expected_output,
                "user_output": user_output,
                "is_correct": is_correct
            })

        save_user_progress(problem_id, code, all_correct)

        return jsonify({
            "result": results,
            "correct": all_correct,
            "message": "All test cases passed!" if all_correct else "Some test cases failed."
        })

    finally:
        # Clean up temporary files
        if os.path.exists(TEMP_DIR):
            for file in os.listdir(TEMP_DIR):
                os.remove(os.path.join(TEMP_DIR, file))




@app.route('/record_clipboard_event', methods=['POST'])
def record_clipboard_event():
    """Record clipboard events with timestamps."""
    data = request.json
    action = data.get("action")
    content = data.get("content")
    timestamp = data.get("timestamp")
    question_id = data.get("question_id")

    # Add server-side timestamp
    server_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_path = os.path.join(CLIPBOARD_DIR, f"clipboard_q{question_id}.txt")

    with open(file_path, 'a') as f:
        f.write(f"[{server_timestamp}] {timestamp} - {action.upper()}:\n{content}\n----\n")

    return jsonify({"message": "Clipboard event recorded successfully"})


@app.route('/favicon.ico')
def favicon():
    """Serve the favicon.ico file."""
    return send_from_directory(os.path.abspath("."), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/chat', methods=['POST'])
def chat():
    """Handle ChatGPT interactions with timestamps."""
    data = request.json
    user_message = data.get('message')
    editor_content = data.get('context', '')
    question_id = data.get('question_id')

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant. Answer only the questions asked after the java code."},
                {"role": "user", "content": f"Here's my current Java code:\n\n{editor_content}\n\n{user_message}"}
            ],
            max_tokens=300,
            temperature=0
        )

        assistant_response = response['choices'][0]['message']['content'].strip()

        # Log with timestamp
        file_path = os.path.join(CHAT_LOGS_DIR, f"chat_log_q{question_id}.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(file_path, 'a') as f:
            f.write(f"[{timestamp}] User: {user_message}\n")
            f.write(f"[{timestamp}] Editor Context:\n{editor_content}\n")
            f.write(f"[{timestamp}] Assistant: {assistant_response}\n")
            f.write("----\n")

        return jsonify({"response": assistant_response})
    except Exception as e:
        return jsonify({"response": f"Error communicating with assistant: {str(e)}"})


def save_user_progress(problem_id, code, is_correct):
    """Save user progress for a specific question with a timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_path = os.path.join(USER_PROGRESS_DIR, f"user_progress_q{problem_id}.txt")

    with open(file_path, 'a') as f:
        status = "Correct" if is_correct else "Incorrect"
        f.write(f"[{timestamp}] Status: {status}\n")
        f.write(f"Code:\n{code}\n")
        f.write("----\n")


def open_browser():
    """Open the app in the default web browser."""
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open("http://localhost:8000")


if __name__ == '__main__':
    Timer(1, open_browser).start()
    app.run(debug=True, port=8000)
