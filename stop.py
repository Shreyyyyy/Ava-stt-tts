#!/usr/bin/env python3
"""
Stop AVA Sarvam AI Voice Interface servers
Kills both backend and frontend processes
"""

import subprocess
import sys
import time
import signal
import os

def find_and_kill_process(port):
    """Find and kill process using the specified port"""
    try:
        # Find process using the port
        result = subprocess.run(
            ['lsof', '-t', '-i', f':{port}'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid.strip():
                    try:
                        os.kill(int(pid.strip()), signal.SIGTERM)
                        print(f"✓ Sent SIGTERM to process {pid.strip()} on port {port}")
                        time.sleep(1)  # Give process time to terminate
                        
                        # Force kill if still running
                        try:
                            os.kill(int(pid.strip()), 0)  # Check if still exists
                            os.kill(int(pid.strip()), signal.SIGKILL)
                            print(f"✓ Forced kill of process {pid.strip()} on port {port}")
                        except ProcessLookupError:
                            pass  # Process already terminated
                    except (ProcessLookupError, ValueError) as e:
                        print(f"✗ Error killing process {pid.strip()}: {e}")
        else:
            print(f"ℹ No process found on port {port}")
            
    except FileNotFoundError:
        print("✗ lsof command not found. Trying alternative method...")
        kill_by_port_alternative(port)
    except Exception as e:
        print(f"✗ Error finding process on port {port}: {e}")

def kill_by_port_alternative(port):
    """Alternative method to kill processes using netstat and ps"""
    try:
        # Use netstat to find process
        result = subprocess.run(
            ['netstat', '-tulpn', '|', 'grep', f':{port}'],
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 7:
                        pid = parts[6].split('/')[0]
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            print(f"✓ Killed process {pid} on port {port}")
                        except (ProcessLookupError, ValueError) as e:
                            print(f"✗ Error killing process {pid}: {e}")
        else:
            print(f"ℹ No process found on port {port}")
            
    except Exception as e:
        print(f"✗ Alternative method failed: {e}")

def kill_by_name():
    """Kill processes by name"""
    processes_to_kill = [
        'uvicorn',
        'python -m http.server',
        'serve_frontend.py'
    ]
    
    for process_name in processes_to_kill:
        try:
            result = subprocess.run(
                ['pkill', '-f', process_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✓ Killed processes matching: {process_name}")
        except FileNotFoundError:
            print(f"✗ pkill command not found")
        except Exception as e:
            print(f"✗ Error killing {process_name}: {e}")

def main():
    print("🛑 Stopping AVA Sarvam AI Voice Interface")
    print("=" * 45)
    
    # Kill by ports first (more precise)
    print("🔍 Checking for processes on ports 8000 and 3001...")
    find_and_kill_process(8000)  # Backend
    find_and_kill_process(3001)  # Frontend
    
    # Also kill by name as backup
    print("\n🔍 Checking for processes by name...")
    kill_by_name()
    
    # Wait a moment and verify
    time.sleep(2)
    
    print("\n🔍 Verifying processes are stopped...")
    still_running = False
    
    for port in [8000, 3001]:
        try:
            result = subprocess.run(
                ['lsof', '-t', '-i', f':{port}'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                print(f"⚠ Process still running on port {port}")
                still_running = True
            else:
                print(f"✓ Port {port} is clear")
        except:
            pass
    
    if still_running:
        print("\n⚠ Some processes may still be running. You may need to kill them manually.")
        print("Try: lsof -i:8000 and lsof -i:3001 to check")
    else:
        print("\n✅ All AVA servers stopped successfully!")
    
    print("=" * 45)

if __name__ == "__main__":
    main()
