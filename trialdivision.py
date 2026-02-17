#!/usr/bin/env python3
import argparse
import csv
import math
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict

# ----------------------------
# Trial Divisoin
# ----------------------------
def trial_division(n: int, timeout_s: float | None = None) -> Dict:
    start_ns = time.perf_counter_ns()
    deadline_ns = start_ns + int(timeout_s * 1_000_000_000) if timeout_s else None

    result = {
        "N": int(n),
        "bits_N": int(n.bit_length() if n >= 0 else 0),
        "status": "INVALID",
        "factors": [],
        "residual": int(n),
        "trials_tested": 0,
        "divisions": 0,
        "duration_ns": 0,
        "duration_ms": 0.0,
        "duration_s": 0.0,
    }

    if n is None or n < 2:
        end_ns = time.perf_counter_ns()
        result["duration_ns"] = end_ns - start_ns
        result["duration_ms"] = result["duration_ns"] / 1_000_000.0
        result["duration_s"] = result["duration_ns"] / 1_000_000_000.0
        result["status"] = "INVALID"
        result["residual"] = int(n)
        return result

    factors: List[Tuple[int, int]] = []
    residual = n
    trials = 0
    divisions = 0

    # Faktor 2
    e2 = 0
    while residual % 2 == 0:
        divisions += 1
        residual //= 2
        e2 += 1
        if deadline_ns and time.perf_counter_ns() >= deadline_ns:
            end_ns = time.perf_counter_ns()
            result.update({
                "factors": factors + ([(2, e2)] if e2 else []),
                "residual": int(residual),
                "trials_tested": trials,
                "divisions": divisions,
                "status": "TIMEOUT",
            })
            result["duration_ns"] = end_ns - start_ns
            result["duration_ms"] = result["duration_ns"] / 1_000_000.0
            result["duration_s"] = result["duration_ns"] / 1_000_000_000.0
            return result
    if e2:
        factors.append((2, e2))

    # Faktor 3
    e3 = 0
    while residual % 3 == 0:
        divisions += 1
        residual //= 3
        e3 += 1
        if deadline_ns and time.perf_counter_ns() >= deadline_ns:
            end_ns = time.perf_counter_ns()
            result.update({
                "factors": factors + ([(3, e3)] if e3 else []),
                "residual": int(residual),
                "trials_tested": trials,
                "divisions": divisions,
                "status": "TIMEOUT",
            })
            result["duration_ns"] = end_ns - start_ns
            result["duration_ms"] = result["duration_ns"] / 1_000_000.0
            result["duration_s"] = result["duration_ns"] / 1_000_000_000.0
            return result
    if e3:
        factors.append((3, e3))

    # wenn 6k±1 Kandidaten dann
    i = 5
    step = 2
    while i * i <= residual:
        trials += 1
        if residual % i == 0:
            ei = 0
            while residual % i == 0:
                divisions += 1
                residual //= i
                ei += 1
                if deadline_ns and time.perf_counter_ns() >= deadline_ns:
                    end_ns = time.perf_counter_ns()
                    if ei:
                        factors.append((i, ei))
                    result.update({
                        "factors": factors,
                        "residual": int(residual),
                        "trials_tested": trials,
                        "divisions": divisions,
                        "status": "TIMEOUT",
                    })
                    result["duration_ns"] = end_ns - start_ns
                    result["duration_ms"] = result["duration_ns"] / 1_000_000.0
                    result["duration_s"] = result["duration_ns"] / 1_000_000_000.0
                    return result
            factors.append((i, ei))
        i += step
        step = 6 - step
        if deadline_ns and time.perf_counter_ns() >= deadline_ns:
            end_ns = time.perf_counter_ns()
            result.update({
                "factors": factors,
                "residual": int(residual),
                "trials_tested": trials,
                "divisions": divisions,
                "status": "TIMEOUT",
            })
            result["duration_ns"] = end_ns - start_ns
            result["duration_ms"] = result["duration_ns"] / 1_000_000.0
            result["duration_s"] = result["duration_ns"] / 1_000_000_000.0
            return result

    # Rest
    if residual > 1:
        factors.append((residual, 1))
        status = "PRIME" if len(factors) == 1 and factors[0][1] == 1 and factors[0][0] == n else "FOUND_ALL"
    else:
        status = "FOUND_ALL"

    end_ns = time.perf_counter_ns()
    result.update({
        "factors": factors,
        "residual": int(1 if residual == 1 else residual),
        "trials_tested": trials,
        "divisions": divisions,
        "status": status,
    })
    result["duration_ns"] = end_ns - start_ns
    result["duration_ms"] = result["duration_ns"] / 1_000_000.0
    result["duration_s"] = result["duration_ns"] / 1_000_000_000.0
    return result

def format_factorization(factors: List[Tuple[int, int]]) -> str:
    return " * ".join([f"{p}^{e}" if e > 1 else f"{p}" for (p, e) in factors]) if factors else ""

def read_n_file(path: Path) -> List[int]:
    ns: List[int] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            ns.append(int(s))
    return ns

def run_one_file(input_txt: Path, out_csv: Path, timeout_s: int):
    ns = read_n_file(input_txt)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "N", "bits_N", "status",
        "factors_str", "residual",
        "trials_tested", "divisions",
        "duration_ns", "duration_ms", "duration_s",
        "source_file", "started_utc", "finished_utc",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for n in ns:
            t0 = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            res = trial_division(n, timeout_s=timeout_s)
            t1 = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            row = {
                "N": res["N"],
                "bits_N": res["bits_N"],
                "status": res["status"],
                "factors_str": format_factorization(res["factors"]),
                "residual": res["residual"],
                "trials_tested": res["trials_tested"],
                "divisions": res["divisions"],
                "duration_ns": res["duration_ns"],
                "duration_ms": res["duration_ms"],
                "duration_s": res["duration_s"],
                "source_file": str(input_txt),
                "started_utc": t0,
                "finished_utc": t1,
            }
            w.writerow(row)

def main():
    ap = argparse.ArgumentParser(
        description="Trial Division: verarbeitet automatisch TXT-Dateien n_values_XXXbit.txt für Bitlängen 8..100 (Schritt 4) und erzeugt je eine CSV."
    )
    ap.add_argument(
        "--input-dir",
        type=str,
        default=r"C:\Users\Verena Gemmel\Documents\Jonathan Schule\Facharbeit\Versuche und Ergebnisse\Experiment Trial Division\Programme\n_values",
        help="Ordner mit den n_values_XXXbit.txt Dateien."
    )
    ap.add_argument(
        "--output-dir",
        type=str,
        default=r"C:\Users\Verena Gemmel\Documents\Jonathan Schule\Facharbeit\Versuche und Ergebnisse\Experiment Trial Division\Programme\results_trial_division",
        help="Ausgabeordner für CSV-Dateien."
    )
    ap.add_argument("--timeout", type=int, default=30, help="Timeout pro Zahl in Sekunden (default: 30).")
    args = ap.parse_args()

    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bit_lengths = list(range(8, 101, 4))
    for bits in bit_lengths:
        name = f"n_values_{bits:03d}bit.txt"
        in_file = in_dir / name
        if not in_file.exists():
            print(f"⚠️ Datei fehlt: {in_file}")
            continue
        out_file = out_dir / f"results_trial_{bits:03d}bit.csv"
        print(f"→ {bits:3d} Bit: {in_file} → {out_file}")
        run_one_file(in_file, out_file, timeout_s=args.timeout)

    print("✓ Fertig.")

if __name__ == "__main__":
    main()