import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
# OpenShift will inject these variables from your Secret or Deployment
DB_HOST = os.environ.get('DB_HOST', 'budget-db')
DB_NAME = os.environ.get('POSTGRESQL_DATABASE', 'budget_db')
DB_USER = os.environ.get('POSTGRESQL_USER', 'budgetuser')
DB_PASS = os.environ.get('POSTGRESQL_PASSWORD', 'budgetpass')

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=5432
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

# Example Route
@app.route('/')
def index():
    conn = get_db_connection()
    # Your logic here...
    return render_template('index.html')

if __name__ == '__main__':
    # OpenShift expects the app to listen on 0.0.0.0
    app.run(host='0.0.0.0', port=8080)