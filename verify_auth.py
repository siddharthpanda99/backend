import time
import requests
import sys
import subprocess
import os
import signal

# Configuration
BASE_URL = "http://127.0.0.1:8000/api/v1"
EMAIL = f"test_{int(time.time())}@example.com"
USERNAME = f"user_{int(time.time())}"
PASSWORD = "password123"

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
        # 2. Register
        print(f"Registering user: {EMAIL}...")
        reg_payload = {
            "email": EMAIL,
            "username": USERNAME,
            "password": PASSWORD,
            "full_name": "Test User",
            "confirm_password": PASSWORD
        }
        res = requests.post(f"{BASE_URL}/auth/register", json=reg_payload)
        if res.status_code == 200:
            print_result("Register", "SUCCESS", res.json())
        else:
            print_result("Register", "FAILED", f"{res.status_code} {res.text}")
            return

        # 3. Login
        print("Logging in...")
        login_payload = {
            "email": EMAIL,
            "password": PASSWORD
        }
        res = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
        if res.status_code == 200:
            token_data = res.json()['data']
            access_token = token_data['access_token']
            print_result("Login", "SUCCESS", "Token acquired")
        else:
            print_result("Login", "FAILED", f"{res.status_code} {res.text}")
            return

        # 4. Get Me (Private)
        print("Fetching Profile (/me)...")
        headers = {"Authorization": f"Bearer {access_token}"}
        res = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        if res.status_code == 200:
            print_result("Get Me", "SUCCESS", res.json())
        else:
            print_result("Get Me", "FAILED", f"{res.status_code} {res.text}")

        # 5. Admin Only (Should Fail for standard user)
        # Note: RoleChecker checks if user has 'admin' role. Created user has no roles or default roles.
        # We expect 403.
        print("Testing Admin Route (/admin-only)...")
        res = requests.get(f"{BASE_URL}/auth/admin-only", headers=headers)
        if res.status_code == 403:
            print_result("Admin Access", "SUCCESS", "Access Denied as expected")
        elif res.status_code == 200:
            print_result("Admin Access", "WARNING", "Access Allowed (Unexpected for new user)")
        else:
            print_result("Admin Access", "FAILED", f"Unexpected status: {res.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")
        # Print server output for debugging
        stdout, stderr = server_process.communicate(timeout=10)
        print("SERVER STDOUT:", stdout)
        print("SERVER STDERR:", stderr)
    finally:
        print("Stopping server...")
        server_process.terminate()
        # server_process.kill()

if __name__ == "__main__":
    run_verification()
