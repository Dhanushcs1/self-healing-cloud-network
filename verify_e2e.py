import subprocess
import time
import requests
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

procs = []
try:
    print("Starting 3 Cloud Servers...")
    for i in [1, 2, 3]:
        env = os.environ.copy()
        env['SERVER_NAME'] = f'Cloud Server {i}'
        env['SERVER_ID'] = str(i)
        env['PORT'] = str(5000 + i)
        p = subprocess.Popen(
            [sys.executable, os.path.join(BASE_DIR, 'servers', 'server.py')],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        procs.append(p)

    time.sleep(2)

    print("Starting Main Application (app.py)...")
    app_proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, 'app.py')],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    procs.append(app_proc)

    time.sleep(3)

    print("\n--- 1. Testing /api/dashboard/stats ---")
    stats = requests.get('http://localhost:5000/api/dashboard/stats').json()
    print("Stats Response:", stats)

    print("\n--- 2. Testing /api/request (Round Robin - 6 requests) ---")
    servers_hit = []
    for req_num in range(6):
        r = requests.get('http://localhost:5000/api/request').json()
        sid = r.get('server_id')
        sname = r.get('server_name')
        rt = r.get('response_time')
        servers_hit.append(sid)
        print(f"Req #{req_num+1}: Dispatched to Server {sid} ({sname}) in {rt}s")

    print("\nDispatch Pattern:", servers_hit)
    assert servers_hit == [1, 2, 3, 1, 2, 3], f"Unexpected distribution: {servers_hit}"
    print(">> Round Robin Verified Perfectly! (1 -> 2 -> 3 -> 1 -> 2 -> 3)")

    print("\n--- 3. Testing /api/load-balancer/statistics ---")
    lb_stats = requests.get('http://localhost:5000/api/load-balancer/statistics').json()
    print("LB Statistics:", lb_stats)

    print("\n--- 4. Testing /api/monitoring/status ---")
    mon_status = requests.get('http://localhost:5000/api/monitoring/status').json()
    print("Monitoring nodes tracked:", list(mon_status.keys()))

    print("\n--- 5. Testing Simulation Endpoint (Simulating Server 2 Failure) ---")
    fail_res = requests.post('http://localhost:5000/api/simulation/failure/2').json()
    print("Failure simulation response:", fail_res)

    print("\n==========================================")
    print("ALL CORE INTEGRATION TESTS PASSED 100%!")
    print("==========================================")

finally:
    print("\nTerminating test processes...")
    for p in procs:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("Clean up finished.")
