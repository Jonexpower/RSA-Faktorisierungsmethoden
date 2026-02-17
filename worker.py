#!/usr/bin/env python3
import os, socket, time, requests
from datetime import datetime
from pollardrhov6 import pollard_rho_seeded

MASTER_URL = os.environ.get("MASTER_URL", "http://master:5000")
WORKER_ID  = os.environ.get("WORKER_ID", socket.gethostname())

def get_next_task():
    try:
        r = requests.get(f"{MASTER_URL}/next-task", params={"worker_id": WORKER_ID}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[{WORKER_ID}] Fehler beim Abholen der Aufgabe: {e}")
        return None

def submit_result(task: dict, result: dict):
    payload = {
        "job_id": task["job_id"],
        "race_index": task.get("race_index"),
        "attempt": task.get("attempt"),
        "worker_id": WORKER_ID,
        "timeout_s": task.get("timeout_s"),
        "source_file": task.get("source_file",""),
        "started_utc": result.get("started_utc",""),
        "finished_utc": result.get("finished_utc",""),
        "result": result,
    }
    try:
        r = requests.post(f"{MASTER_URL}/submit-result", json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[{WORKER_ID}] Fehler beim Senden des Ergebnisses: {e}")
        return False

def main_loop():
    print(f"[{WORKER_ID}] Verbinde mit Master {MASTER_URL}")
    while True:
        data = get_next_task()
        if not data:
            time.sleep(2); continue
        if data.get("status") == "empty":
            print(f"[{WORKER_ID}] Keine Aufgaben mehr. Warte 10s …")
            time.sleep(10); continue
        if data.get("status") != "ok":
            print(f"[{WORKER_ID}] Unerwartete Antwort: {data}")
            time.sleep(2); continue

        task = data["task"]
        seed = int(task["seed"])
        n = int(task["N"])
        timeout_s = int(task["timeout_s"])

        t0 = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        res = pollard_rho_seeded(n, seed=seed, timeout_s=timeout_s)
        t1 = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        res["started_utc"] = t0
        res["finished_utc"] = t1

        ok = submit_result(task, res)
        msg = "OK" if ok else "Fehler"
        print(f"[{WORKER_ID}] {msg} Job {task['job_id']}: status={res['status']} duration_s={res['duration_s']:.6f}")
        time.sleep(0.5)

if __name__ == "__main__":
    main_loop()
