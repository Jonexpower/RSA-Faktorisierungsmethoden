#!/usr/bin/env python3
import argparse
import csv
import time
from math import isqrt

def fermat_factor(N: int, timeout_s: float = 0.0, max_iter: int = 0):
    """
    Fermat factorization:
      a = ceil(sqrt(N)); increment a until a^2 - N is a perfect square b^2.
    Returns ((p, q), iterations) if found, otherwise (None, iterations).
    """
    a = isqrt(N)
    if a * a < N:
        a += 1

    iterations = 0
    t0 = time.perf_counter()

    while True:
        if timeout_s and (time.perf_counter() - t0) > timeout_s:
            return None, iterations
        if max_iter and iterations >= max_iter:
            return None, iterations

        b2 = a * a - N
        b = isqrt(b2)
        if b * b == b2:
            p = a - b
            q = a + b
            return (p, q), iterations

        a += 1
        iterations += 1  # Iterationen zählen

def main():
    ap = argparse.ArgumentParser("Measure Fermat factorization time vs Δ")
    ap.add_argument("--in", dest="inp", required=True, help="Input CSV from generator")
    ap.add_argument("--out", dest="out", required=True, help="Output CSV with results")
    ap.add_argument("--timeout", type=float, default=0.0, help="Per-N timeout in seconds (0 = unlimited)")
    ap.add_argument("--max-iter", type=int, default=0, help="Max iterations per N (0 = unlimited)")
    ap.add_argument("--verbose", action="store_true", help="Print per-row progress")
    args = ap.parse_args()

    with open(args.inp, newline="") as f:
        rows = list(csv.DictReader(f))

    out_fields = [
        "bits_p","bits_q","bits_N","N","p_true","q_true",
        "delta","delta_bits","gap","rel_gap",
        "status","p_found","q_found","duration_s","iterations",
        "iter_expected_exact","iter_expected_approx","b","a0","a_target"
    ]
    out = []

    for idx, r in enumerate(rows, 1):
        N = int(r["N"])
        p_true = int(r["p"])
        q_true = int(r["q"])
        delta = int(r["delta"])

        # Theoriegrößen
        s = (p_true + q_true) // 2             # (p+q)/2 als ganze Zahl (beide prim odd → ganzzahlig)
        b = (q_true - p_true) // 2             # (q-p)/2
        a0 = isqrt(N);  a0 = a0 if a0*a0 == N else a0 + 1   # ceil(sqrt(N))
        a_target = s                            # bei Lösung gilt a = (p+q)/2 genau
        iter_expected_exact = max(0, a_target - a0)
        # Approximation aus Taylor: sqrt(s^2 - b^2) ≈ s - b^2/(2s) ⇒ Iterationen ≈ b^2/(2s)
        iter_expected_approx = (b*b) / (2.0 * float(s))

        t0 = time.perf_counter()
        result, iters = fermat_factor(N, timeout_s=args.timeout, max_iter=args.max_iter)
        dt = time.perf_counter() - t0

        if result is not None and result[0] * result[1] == N:
            status = "FOUND"
            p_found, q_found = result
        else:
            status = "TIMEOUT" if args.timeout else ("MAX_ITER" if args.max_iter else "NOT_FOUND")
            p_found = q_found = ""

        if args.verbose:
            print(f"[{idx}/{len(rows)}] Δ={delta}  b={b}  a0={a0}→a*={a_target}  "
                  f"iters={iters}  exact≈{iter_expected_exact}  approx≈{iter_expected_approx:.1f}  "
                  f"time={dt:.6f}s  status={status}")

        out.append({
            "bits_p": int(r["bits_p"]),
            "bits_q": int(r["bits_q"]),
            "bits_N": int(r["bits_N"]),
            "N": N,
            "p_true": p_true,
            "q_true": q_true,
            "delta": delta,
            "delta_bits": int(r["delta_bits"]),
            "gap": int(r["gap"]),
            "rel_gap": float(r["rel_gap"]),
            "status": status,
            "p_found": p_found,
            "q_found": q_found,
            "duration_s": dt,
            "iterations": iters,
            "iter_expected_exact": int(iter_expected_exact),
            "iter_expected_approx": float(iter_expected_approx),
            "b": int(b),
            "a0": int(a0),
            "a_target": int(a_target),
        })

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out)

    print(f"Wrote {len(out)} results to {args.out}")

if __name__ == "__main__":
    main()