import time
import requests
import sys
import subprocess
import os

# Configuration
BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "admin@nexus.ai"
ADMIN_PASSWORD = "admin123"

def print_result(step, status, details=""):
    print(f"[{step}] {status} - {details}", flush=True)

def run_verification():
    # 1. Start Server
    print("Starting server...", flush=True)
    server_process = subprocess.Popen(
        ["./.venv/Scripts/python.exe", "main.py"],
        cwd=os.getcwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    time.sleep(5) 
    
    try:
        # 2. Login as Admin
        print("Logging in as Admin...", flush=True)
        login_payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        res = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
        
        if res.status_code != 200:
             print_result("Admin Login", "FAILED", res.text)
             return
             
        admin_token = res.json()['data']['access_token']
        print_result("Admin Login", "SUCCESS", "Token acquired")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 3. Access Protected Route (e.g., /users, assuming list users is protected)
        # Note: Users router is now protected by default in main.py
        print("Accessing Protected Route as Admin...", flush=True)
        res = requests.get(f"{BASE_URL}/users", headers=admin_headers)
        # If /users is not implemented, we might get 404 or 405, but NOT 401. 
        # If implemented, 200.
        if res.status_code == 401:
            print_result("Admin Access Global", "FAILED", "Got 401 Unauthorized")
        else: 
            print_result("Admin Access Global", "SUCCESS", f"Got {res.status_code} (Authorized)")

        # 4. Access Protected Route without Token
        print("Accessing Protected Route without Token...", flush=True)
        res = requests.get(f"{BASE_URL}/users")
        if res.status_code == 401:
            print_result("Public Access Check", "SUCCESS", "Got 401 Unauthorized")
        else:
            print_result("Public Access Check", "FAILED", f"Expected 401, got {res.status_code}")

        # 5. Public Health Check
        print("Accessing Public Health Endpoint...", flush=True)
        res = requests.get(f"{BASE_URL}/health")
        if res.status_code == 200:
            print_result("Health Check", "SUCCESS", "Got 200 OK")
        else:
            print_result("Health Check", "FAILED", f"Expected 200, got {res.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}", flush=True)
        stdout, stderr = server_process.communicate(timeout=10)
        print("SERVER STDOUT:", stdout, flush=True)
        print("SERVER STDERR:", stderr, flush=True)
    finally:
        print("Stopping server...", flush=True)
        server_process.terminate()

if __name__ == "__main__":
    run_verification()
