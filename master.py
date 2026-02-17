#!/usr/bin/env python3
import argparse, csv, os, threading, hashlib, struct
from datetime import datetime
from flask import Flask, request, jsonify
from pollardrhov6 import read_n_values_for_bits

app = Flask(__name__)

state_lock = threading.Lock()
ns_list = []
race_idx = 0
attempt_next = 1
current = None

attempts_csv = None
summary_csv = None
summary_best = {}     # N -> beste reihen
finished_ns = set()   # Ns, für die weitergeschaltet wurde

results_dir = "/data/results_master"
input_dir = "/data/n_values_equal"
job_list_path = "/data/joblist.txt"
seed_base = 42
timeout_s = 60
bits_start = 40
bits_end = 52
step = 4
workers_count = 0

FIELDS_ATTEMPT = [
    "race_index","attempt","worker_id",
    "N","bits_N","status",
    "p_found","q_found","iterations","restarts",
    "seed","x0","c",
    "duration_ns","duration_ms","duration_s",
    "timeout_s","source_file",
    "started_utc","finished_utc",
]
FIELDS_SUMMARY = [
    "race_index","N","bits_N","source_file",
    "winner_worker","winner_attempt","seed",
    "duration_s","iterations","restarts",
    "started_utc","finished_utc",
]

def ensure_dir(d):
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

def unique_csv_path(path: str) -> str:
    if not path:
        return path
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        cand = f"{base}_{i}{ext}"
        if not os.path.exists(cand):
            return cand
        i += 1

def make_seed(seed_base: int, n: int, attempt: int) -> int:
    h = hashlib.sha256(f"{seed_base}:{n}:{attempt}".encode()).digest()
    return struct.unpack(">Q", h[:8])[0] or 1

def load_job_list(path: str):
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "r") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            n = int(s)
            out.append({"bits": n.bit_length(), "N": n, "source_file": os.path.relpath(path)})
    return out

def build_ns_list_from_bits():
    out = []
    for bits in range(bits_start, bits_end + 1, step):
        ns, src = read_n_values_for_bits(input_dir, bits)
        for n in ns:
            out.append({"bits": bits, "N": n, "source_file": src or ""})
    return out

def bits_label_from_ns(ns):
    bset = {d["bits"] for d in ns}
    if not bset:
        return "unknown"
    if len(bset) == 1:
        return f"{list(bset)[0]}bit"
    return "mixed"

def init_runs(attempts_out: str | None, summary_out: str | None, workers_arg: int):
    global ns_list, race_idx, attempt_next, current, attempts_csv, summary_csv, workers_count, finished_ns, summary_best
    workers_count = int(workers_arg or 0)

    ns_list = load_job_list(job_list_path) or build_ns_list_from_bits()
    summary_best = {}
    finished_ns = set()

    print(f"Master: {len(ns_list)} N-Werte vorbereitet.")
    race_idx = 0
    attempt_next = 1
    current = ns_list[0] if ns_list else None

    ensure_dir(results_dir)
    label = bits_label_from_ns(ns_list)
    wtag = f"w{workers_count if workers_count > 0 else 'unknown'}"

    attempts_name = attempts_out or os.path.join(results_dir, f"attempts_{label}_{wtag}.csv")
    summary_name  = summary_out  or os.path.join(results_dir,  f"summary_{label}_{wtag}.csv")

    attempts_csv = unique_csv_path(attempts_name)
    summary_csv  = unique_csv_path(summary_name)

    with open(attempts_csv, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS_ATTEMPT).writeheader()
    with open(summary_csv, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS_SUMMARY).writeheader()

    print(f"CSV (Attempts): {attempts_csv}")
    print(f"CSV (Summary):  {summary_csv}")

def write_attempt_row(race_index: int, attempt: int, worker_id: str, res: dict, timeout_s_val: int, source_file: str):
    with open(attempts_csv, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS_ATTEMPT).writerow({
            "race_index": race_index, "attempt": attempt, "worker_id": worker_id,
            "N": res.get("N"), "bits_N": res.get("bits_N"), "status": res.get("status"),
            "p_found": res.get("p_found"), "q_found": res.get("q_found"),
            "iterations": res.get("iterations"), "restarts": res.get("restarts"),
            "seed": res.get("seed"), "x0": res.get("x0"), "c": res.get("c"),
            "duration_ns": res.get("duration_ns"), "duration_ms": res.get("duration_ms"),
            "duration_s": res.get("duration_s"),
            "timeout_s": timeout_s_val, "source_file": source_file,
            "started_utc": res.get("started_utc",""), "finished_utc": res.get("finished_utc",""),
        })

def append_summary_row(row: dict):
    with open(summary_csv, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS_SUMMARY).writerow(row)

def update_summary_row(row: dict):
    # Schreibe Datei und ersetze Zeile mit gleichem N
    with open(summary_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for i, r in enumerate(rows):
        if int(r["N"]) == int(row["N"]):
            rows[i] = row
            break
    with open(summary_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS_SUMMARY)
        w.writeheader()
        w.writerows(rows)

def maybe_update_winner_and_advance(race_index: int, attempt: int, worker_id: str, res: dict, source_file: str):
    # Nur bei FOUND abarbeiten
    if res.get("status") != "FOUND":
        return

    n = int(res.get("N"))
    best = summary_best.get(n)
    new_row = {
        "race_index": race_index,
        "N": n,
        "bits_N": res.get("bits_N"),
        "source_file": source_file,
        "winner_worker": worker_id,
        "winner_attempt": attempt,
        "seed": res.get("seed"),
        "duration_s": res.get("duration_s"),
        "iterations": res.get("iterations"),
        "restarts": res.get("restarts"),
        "started_utc": res.get("started_utc",""),
        "finished_utc": res.get("finished_utc",""),
    }

    # Immer den besten in-memory halten
    if (not best) or (float(res.get("duration_s", 0.0)) < float(best["duration_s"])):
        summary_best[n] = new_row
        # Datei:
        if n in finished_ns:
            update_summary_row(new_row)   # Summary-Zeile aktualisieren
        else:
            append_summary_row(new_row)   # erste Zeile schreiben

    # Weiter schalten NUR EINMAL pro N (beim ersten FOUND)
    if n not in finished_ns:
        finished_ns.add(n)
        advance_to_next_N()

def advance_to_next_N():
    global race_idx, attempt_next, current
    race_idx += 1
    if race_idx < len(ns_list):
        current = ns_list[race_idx]
        attempt_next = 1
        print(f"== Wechsel zu nächstem N (index {race_idx}/{len(ns_list)}): bits={current['bits']} N={current['N']} ==")
    else:
        current = None
        print("== Alle N abgearbeitet. ==")

@app.get("/health")
def health():
    with state_lock:
        return jsonify({
            "status": "ok",
            "total_ns": len(ns_list),
            "race_index": race_idx,
            "current_bits": (current or {}).get("bits"),
            "current_N": (current or {}).get("N"),
            "next_attempt": attempt_next if current else None,
            "attempts_csv": attempts_csv,
            "summary_csv": summary_csv,
            "workers": workers_count,
            "finished_count": len(finished_ns),
        })

@app.get("/next-task")
def next_task():
    global attempt_next
    worker_id = request.args.get("worker_id", "").strip() or "unknown"
    with state_lock:
        if not ns_list or current is None:
            return jsonify({"status": "empty"}), 200
        attempt = attempt_next
        attempt_next += 1
        seed = make_seed(seed_base, current["N"], attempt)
        job = {
            "job_id": f"{race_idx}:{current['bits']}:{current['N']}:{attempt}",
            "race_index": race_idx,
            "bits": current["bits"],
            "N": int(current["N"]),
            "attempt": int(attempt),
            "seed": int(seed),
            "timeout_s": int(timeout_s),
            "source_file": current["source_file"],
            "assigned_to": worker_id,
        }
    return jsonify({"status": "ok", "task": job}), 200

@app.post("/submit-result")
def submit_result():
    payload = request.get_json(force=True, silent=False)
    if not payload or "job_id" not in payload or "worker_id" not in payload or "result" not in payload:
        return jsonify({"error": "invalid payload"}), 400
    attempt = int(payload.get("attempt", 0))
    race_index = int(payload.get("race_index", 0))
    worker_id = payload["worker_id"]
    timeout_s_local = int(payload.get("timeout_s", timeout_s))
    source_file = payload.get("source_file","")
    res = payload["result"]

    write_attempt_row(race_index, attempt, worker_id, res, timeout_s_local, source_file)
    with state_lock:
        maybe_update_winner_and_advance(race_index, attempt, worker_id, res, source_file)

    return jsonify({"status": "ok"}), 200

def parse_args():
    ap = argparse.ArgumentParser("Pollard-Rho Master: alle Worker auf gleichem N (Race)")
    ap.add_argument("--job-list", type=str, default="/data/joblist.txt",
                    help="Datei mit N pro Zeile (bevorzugt)")
    ap.add_argument("--input-dir", type=str, default="/data/n_values_equal",
                    help="Fallback: Verzeichnis mit N-Listen (wenn job-list leer ist)")
    ap.add_argument("--results-dir", type=str, default="/data/results_master",
                    help="Zielverzeichnis für CSVs")
    ap.add_argument("--attempts-out", type=str, default=None,
                    help="Dateipfad für Attempts-CSV; bei bestehender Datei wird _1, _2 … angehängt")
    ap.add_argument("--summary-out", type=str, default=None,
                    help="Dateipfad für Summary-CSV; bei bestehender Datei wird _1, _2 … angehängt")
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--bits-start", type=int, default=40)
    ap.add_argument("--bits-end", type=int, default=52)
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", "0") or "0"),
                    help="Anzahl Worker für Dateinamen (w<workers>)")
    ap.add_argument("--bind", type=str, default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5000)
    return ap.parse_args()

def main():
    global input_dir, job_list_path, results_dir, seed_base, timeout_s
    global bits_start, bits_end, step, workers_count
    args = parse_args()
    input_dir = args.input_dir
    job_list_path = args.job_list
    results_dir = args.results_dir
    seed_base = args.seed_base
    timeout_s = args.timeout
    bits_start = args.bits_start
    bits_end = args.bits_end
    step = args.step
    workers_count = args.workers

    init_runs(args.attempts_out, args.summary_out, workers_count)
    print(f"Master startet auf {args.bind}:{args.port} (workers={workers_count})")
    app.run(host=args.bind, port=args.port)

if __name__ == "__main__":
    main()
