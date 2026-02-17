#!/usr/bin/env python3
import argparse
import csv
import math
import random


def is_probable_prime(n: int, k: int = 10) -> bool:
    if n <= 1:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False

    # Schreibe n-1 in die Form d * 2^r
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2

    # Miller-Rabin-Test mit k Durchläufen
    for _ in range(k):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)

        # Falls direkt 1 oder -1 mod n → nächste Runde
        if x in (1, n - 1):
            continue

        for _ in range(r - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False

    return True


def prime_with_bits(bits: int) -> int:
    """
    Erzeugt eine wahrscheinliche Primzahl
    mit exakt der angegebenen Bitlänge.
    """
    lo = 1 << (bits - 1)
    hi = (1 << bits) - 1

    while True:
        # Kandidat erzeugen:
        # MSB setzen (damit Bitlänge stimmt) und ungerade machen
        cand = (random.getrandbits(bits) | lo) | 1

        if cand > hi:
            cand = hi | 1

        if is_probable_prime(cand):
            return cand


def next_prime_up(x: int, hi: int) -> int | None:
    """
    Sucht die nächste wahrscheinliche Primzahl >= x,
    bleibt dabei aber <= hi.
    Falls keine gefunden wird, wird None zurückgegeben.
    """
    if x % 2 == 0:
        x += 1

    while x <= hi:
        if is_probable_prime(x):
            return x
        x += 2

    return None


def gen_row(bits_p: int, bits_q: int, delta: int) -> dict | None:
    """
    Erzeugt ein Semiprime N = p*q,
    wobei der Abstand q - p ungefähr delta entspricht.
    """
    p = prime_with_bits(bits_p)
    hi_q = (1 << bits_q) - 1

    # q wird als nächste Primzahl oberhalb von p + delta gewählt
    q = next_prime_up(p + delta, hi_q)

    if q is None or q.bit_length() != bits_q:
        return None  # falls q nicht passt → neuen Versuch starten

    n = p * q
    gap = abs(q - p)

    # Normierter Abstand (wichtig für Fermat-Analyse)
    rel_gap = gap / math.sqrt(n)

    return {
        "bits_p": bits_p,
        "bits_q": bits_q,
        "bits_N": n.bit_length(),
        "p": p,
        "q": q,
        "N": n,
        "delta": delta,
        "delta_bits": int(round(math.log2(delta))),
        "gap": gap,
        "rel_gap": rel_gap,
    }


def main():
    ap = argparse.ArgumentParser(
        "Erzeugt Semiprimes mit fester Bitlänge für p und q sowie Δ = 2^k"
    )

    ap.add_argument("--b", type=int, required=True,
                    help="Bitlänge für p und q (z.B. 48 → N ≈ 96 Bit)")
    ap.add_argument("--k-list", type=str, required=True,
                    help="Kommagetrennte k-Werte (z.B. 4,8,12,16,20,24,28,32)")
    ap.add_argument("--per-k", type=int, default=2,
                    help="Anzahl der Moduli pro k")
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--seed", type=int, default=42)

    args = ap.parse_args()

    random.seed(args.seed)

    bits_p = args.b
    bits_q = args.b
    ks = [int(s.strip()) for s in args.k_list.split(",") if s.strip()]
    rows: list[dict] = []

    for k in ks:
        delta = 1 << k
        made = 0
        attempts = 0

        while made < args.per_k:
            attempts += 1
            r = gen_row(bits_p, bits_q, delta)

            if r is None:
                continue

            rows.append(r)
            made += 1

        print(f"k={k} (Δ=2^{k}) → {made} Moduli erzeugt in {attempts} Versuchen")

    if not rows:
        raise SystemExit(
            "Keine Werte erzeugt. Eventuell Δ verkleinern oder Bitlänge anpassen."
        )

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} Einträge in Datei {args.out} geschrieben.")


if __name__ == "__main__":
    main()
