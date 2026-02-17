#!/usr/bin/env python3
import argparse
import csv
import hashlib
import os
import time
import random
import math
from datetime import datetime

# ----------------------------
# Pollard-Rho (Floyd, seeded)
# ----------------------------
def pollard_rho_seeded(n, seed, x0=None, c=None, timeout_s=60, max_restarts=10):
    """
    Pollard-Rho mit kontrollierter Zufälligkeit:
    - seed: fester Seed für PRNG (reproduzierbar)
    - x0, c: optional vorgeben; sonst aus PRNG gezogen
    - timeout_s: Zeitlimit pro Versuch
    - max_restarts: wie oft bei d==n neu starten

    Rückgabe: dict mit Laufzeit, Iterationen, gefundenen Faktoren, Seed/x0/c usw.
    """
    rng = random.Random(seed)

    def draw_params():
        xi = x0 if x0 is not None else rng.randrange(2, n - 1)
        ci = c  if c  is not None else rng.randrange(1, n - 1)
        return xi, ci

    def f(x, c_):
        return (x * x + c_) % n

    iterations = 0
    restarts = 0
    status = "FOUND"
    p_found = 0
    q_found = 0

    x_start, c_start = draw_params()
    x = x_start
    y = x_start
    c_used = c_start

    start_ns = time.perf_counter_ns()
    deadline_ns = start_ns + int(timeout_s * 1_000_000_000)

    while True:
        # Floyd cycle detection
        x = f(x, c_used)
        y = f(y, c_used)
        y = f(y, c_used)
        iterations += 1

        d = math.gcd(abs(x - y), n)

        # Timeout?
        now_ns = time.perf_counter_ns()
        if now_ns >= deadline_ns:
            status = "TIMEOUT"
            break

        if d == 1:
            continue
        if d == n:
            # unglückliche Parameter – Restart mit neuen x0,c
            restarts += 1
            if restarts > max_restarts:
                status = "RESTART_LIMIT"
                break
            x_start, c_start = draw_params()
            x = x_start
            y = x_start
            c_used = c_start
            continue

        # echter Faktor gefunden
        p_found = d
        q_found = n // d
        break

    end_ns = time.perf_counter_ns()
    duration_ns = end_ns - start_ns

    return {
        "N": n,
        "bits_N": n.bit_length(),
        "status": status,
        "p_found": int(p_found),
        "q_found": int(q_found),
        "iterations": int(iterations),
        "restarts": int(restarts),
        "seed": int(seed),
        "x0": int(x_start),
        "c": int(c_start),
        "duration_ns": int(duration_ns),
        "duration_us": duration_ns / 1_000.0,
        "duration_ms": duration_ns / 1_000_000.0,
        "duration_s": duration_ns / 1_000_000_000.0,
    }

# ----------------------------
# Seed-Ableitung (stabil)
# ----------------------------
def derive_seed(seed_base: int, n: int, repeat: int) -> int:
    """
    Deterministischer 64-bit Seed aus seed_base, N und Wiederholung.
    Unabhängig von Reihenfolge der Experimente.
    """
    h = hashlib.sha256(f"{seed_base}:{n}:{repeat}".encode()).digest()
    return int.from_bytes(h[:8], "big")

# ----------------------------
# I/O-Helfer
# ----------------------------
def read_n_values_for_bits(input_dir: str, bits: int):
    """
    Liest N-Werte für die gegebene Bitlänge aus input_dir.
    Unterstützt beide Dateinamen:
      - n_values_equal_{bits:03d}bit.txt
      - n_values_{bits:03d}bit.txt
    """
    candidates = [
        os.path.join(input_dir, f"n_values_equal_{bits:03d}bit.txt"),
        os.path.join(input_dir, f"n_values_{bits:03d}bit.txt"),
    ]
    path = None
    for c in candidates:
        if os.path.isfile(c):
            path = c
            break
    if not path:
        raise FileNotFoundError(f"Keine N-Datei für {bits} Bit in {input_dir} gefunden. Erwartet: {candidates[0]} oder {candidates[1]}")

    ns = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                ns.append(int(line))
    return ns, path

def ensure_dir(d):
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

# ----------------------------
# Batch-Runner
# ----------------------------
def run_bitlength_for_seed(seed_base: int, bits: int, ns: list, repeats: int, timeout_s: int, out_csv_path: str):
    """
    Führt für eine Bitlänge und einen seed_base alle Ns mit 'repeats' Wiederholungen aus
    und schreibt ein CSV für diese Bitlänge und diesen Seed.
    Gibt alle Zeilen (Dicts) zurück, um sie später in eine Gesamt-CSV pro Seed zu aggregieren.
    """
    ensure_dir(os.path.dirname(out_csv_path))
    fieldnames = [
        "N", "bits_N", "repeat", "timeout_s", "status",
        "p_found", "q_found", "iterations", "restarts",
        "seed", "x0", "c",
        "duration_ns", "duration_us", "duration_ms", "duration_s",
        "started_utc", "finished_utc",
        "source_file",
    ]
    rows = []
    with open(out_csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for n in ns:
            for r in range(1, repeats + 1):
                seed = derive_seed(seed_base, n, r)
                t0 = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                res = pollard_rho_seeded(n, seed=seed, timeout_s=timeout_s)
                t1 = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                row = {
                    **res,
                    "repeat": r,
                    "timeout_s": timeout_s,
                    "started_utc": t0,
                    "finished_utc": t1,
                    "source_file": "",  # wird vom Caller gesetzt
                }
                w.writerow(row)
                rows.append(row)
    return rows

def run_all_bits_for_seeds(input_dir: str, results_dir: str, seeds: list, repeats: int, timeout_s: int):
    """
    Läuft über Bitlängen 8..100 in 4er-Schritten.
    Für jede Bitlänge und jeden Seed:
      - liest N-Liste
      - erzeugt per-Bitlängen-CSV unter results_dir/{seed}/
    Zusätzlich:
      - pro Seed eine Gesamt-CSV über alle Bitlängen.
    """
    bit_lengths = list(range(8, 101, 4))
    ensure_dir(results_dir)

    for seed_base in seeds:
        all_rows = []
        seed_dir = os.path.join(results_dir, f"seed_{seed_base}")
        ensure_dir(seed_dir)

        print(f"== Seed {seed_base} ==")
        for bits in bit_lengths:
            ns, src_path = read_n_values_for_bits(input_dir, bits)
            out_csv = os.path.join(seed_dir, f"results_{bits:03d}bit_seed{seed_base}.csv")
            rows = run_bitlength_for_seed(seed_base, bits, ns, repeats, timeout_s, out_csv)
            # ergänze source_file für jeden Row
            for r in rows:
                r["source_file"] = os.path.relpath(src_path)
            all_rows.extend(rows)
            print(f"  ✓ {bits:3d} Bit → {len(rows)} Läufe → {out_csv}")

        # Gesamt-CSV pro Seed
        all_csv = os.path.join(seed_dir, f"results_seed{seed_base}_allbits.csv")
        fieldnames = [
            "N", "bits_N", "repeat", "timeout_s", "status",
            "p_found", "q_found", "iterations", "restarts",
            "seed", "x0", "c",
            "duration_ns", "duration_us", "duration_ms", "duration_s",
            "started_utc", "finished_utc",
            "source_file",
        ]
        with open(all_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in all_rows:
                w.writerow(row)
        print(f"  ✓ Gesamt-CSV für Seed {seed_base}: {all_csv}\n")

# ----------------------------
# CLI
# ----------------------------
def parse_args():
    ap = argparse.ArgumentParser(
        description="Pollard-Rho Runner: zwei Seeds (z. B. 42 und 1024) über Bitlängen 8..100; CSV pro Bitlänge und eine Gesamt-CSV pro Seed."
    )
    ap.add_argument("--input-dir", type=str, default="n_values_equal",
                    help="Verzeichnis mit N-Listen-Dateien (n_values_equal_XXXbit.txt oder n_values_XXXbit.txt)")
    ap.add_argument("--results-dir", type=str, default="results",
                    help="Ausgabeverzeichnis für CSV-Dateien (wird pro Seed unterteilt)")
    ap.add_argument("--seeds", type=str, default="42,1024",
                    help="Kommagetrennte Liste von seed_base Werten (default: 42,1024)")
    ap.add_argument("--repeats", type=int, default=3,
                    help="Anzahl Wiederholungen (Seeds) pro N (default: 3)")
    ap.add_argument("--timeout", type=int, default=60,
                    help="Timeout pro Lauf in Sekunden (default: 60)")
    return ap.parse_args()

def main():
    args = parse_args()
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    run_all_bits_for_seeds(
        input_dir=args.input_dir,
        results_dir=args.results_dir,
        seeds=seeds,
        repeats=args.repeats,
        timeout_s=args.timeout,
    )
    print("Fertig.")

if __name__ == "__main__":
    main()