#!/usr/bin/env python3
import random
import math
import os
from datetime import datetime

# ------------------------------
# Primzahl-Tools
# ------------------------------

def is_prime(n, k=8):
    """
    Miller-Rabin Primality Test.
    k = Anzahl der zufälligen Basen (Genauigkeit).
    """
    if n <= 1:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False

    # Schreibe n-1 als d * 2^r
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2

    # k Runden Miller-Rabin
    for _ in range(k):
        a = random.randint(2, n - 2)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def generate_prime_within_range(lower_bound, upper_bound, max_attempts=200000):
    """
    Erzeugt eine Primzahl im inklusiven Bereich [lower_bound, upper_bound].
    Wirft ValueError, falls keine gefunden wird.
    """
    if lower_bound > upper_bound:
        raise ValueError(f"Ungültiger Bereich: [{lower_bound}, {upper_bound}]")

    # Zufällige Versuche
    for _ in range(max_attempts):
        candidate = random.randint(lower_bound, upper_bound)
        if is_prime(candidate):
            return candidate

    # Fallback: sequenzielle Suche (von beiden Seiten)
    for candidate in range(lower_bound, upper_bound + 1):
        if is_prime(candidate):
            return candidate
    for candidate in range(upper_bound, lower_bound - 1, -1):
        if is_prime(candidate):
            return candidate

    raise ValueError(f"Keine Primzahl gefunden in Bereich [{lower_bound}, {upper_bound}]")


def get_all_primes_up_to(n):
    """
    Eratosthenes-Sieb für alle Primzahlen bis n.
    Schnell für kleine n (< ~5 Mio).
    """
    if n < 2:
        return []
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    step = int(n ** 0.5)
    for i in range(2, step + 1):
        if sieve[i]:
            i2 = i * i
            sieve[i2:n + 1:i] = [False] * (((n - i2) // i) + 1)
    return [i for i in range(2, n + 1) if sieve[i]]


# ------------------------------
# Hilfsfunktionen
# ------------------------------

def validate_bitlength(n, expected_bits):
    """
    Validiert, ob N EXAKT die erwartete Bitlänge hat.
    """
    actual_bits = n.bit_length()
    lower_bound = 2 ** (expected_bits - 1)
    upper_bound = (2 ** expected_bits) - 1

    if actual_bits != expected_bits:
        return False, actual_bits, f"Bitlänge {actual_bits} statt {expected_bits}"
    if not (lower_bound <= n <= upper_bound):
        return False, actual_bits, f"Außerhalb Bereich [{lower_bound}, {upper_bound}]"
    return True, actual_bits, "OK"


def bounds_for_bits(b):
    """
    Liefert (lower, upper) für b-Bit-Zahlen.
    """
    lower = 2 ** (b - 1)
    upper = (2 ** b) - 1
    return lower, upper


def choose_equal_factor_bits_for_target_N_bits(target_bits):
    """
    Wähle die Bitlänge b für p und q (gleich lang), sodass
    p und q b-Bit sind und p*q potentiell target_bits haben kann.

    - Für gerade target_bits typischerweise b = target_bits // 2
    - Für ungerade target_bits nehmen wir b = ceil(target_bits / 2),
      testen aber beim Erzeugen streng die Ziel-Bitlänge.
    """
    if target_bits <= 1:
        raise ValueError("target_bits muss >= 2 sein")
    # p und q sollen GLEICHE Bitlänge haben:
    b = (target_bits + 1) // 2  # ceil(target_bits / 2)
    return b


# ------------------------------
# Erzeugung gleich langer p/q
# ------------------------------

def generate_n_values_equal_factor_bits_small(bits, count):
    """
    Für kleine target_bits (8-28) enumerieren wir p, q mit gleicher Bitlänge b
    und sammeln gültige N = p*q mit EXAKT 'bits'.
    """
    b = choose_equal_factor_bits_for_target_N_bits(bits)
    p_lower, p_upper = bounds_for_bits(b)

    print(f"  Ziel-Bitlänge N: {bits} Bit")
    print(f"  Faktor-Bitlänge: p, q = {b} Bit (gleich)")
    print(f"  Strategie: Enumeration (kleine Bitlängen)")
    print(f"  Bereiche: p,q ∈ [{p_lower}, {p_upper}]")

    # Alle Primzahlen bis p_upper vorrechnen
    primes = [p for p in get_all_primes_up_to(p_upper) if p >= p_lower]
    print(f"  Verfügbare {b}-Bit Primzahlen: {len(primes)}")

    valid_ns = set()
    rejected = 0

    # p,q-Kombinationen mit gleicher Bitlänge (beide in 'primes' sind bereits b-Bit)
    for i, p in enumerate(primes):
        # Frühes Abbrechen: p*p minimal — wenn das schon > maximal N für 'bits', dann fertig
        for j in range(i, len(primes)):  # j >= i erlaubt p=q
            q = primes[j]
            n = p * q
            is_ok, actual_bits, err = validate_bitlength(n, bits)
            if is_ok:
                valid_ns.add(n)
            else:
                rejected += 1
                # Zeige nur wenige Beispiele
                if rejected <= 3:
                    print(f"    ⚠️ Abgelehnt: N={n}, p={p}, q={q} → {err}")

    valid_sorted = sorted(valid_ns)
    print(f"  Gefunden: {len(valid_sorted)} gültige N (p,q gleich-bittig)")

    if len(valid_sorted) == 0:
        print(" Keine gültigen N gefunden – versuche b-1 als Fallback.")
        # Fallback: b-1 (nur wenn sinnvoll)
        if b > 2:
            b2 = b - 1
            p_lower, p_upper = bounds_for_bits(b2)
            primes = [p for p in get_all_primes_up_to(p_upper) if p >= p_lower]
            print(f"  Fallback mit b={b2} → Primzahlen: {len(primes)}")
            for i, p in enumerate(primes):
                for j in range(i, len(primes)):
                    q = primes[j]
                    n = p * q
                    is_ok, _, _ = validate_bitlength(n, bits)
                    if is_ok:
                        valid_ns.add(n)
            valid_sorted = sorted(valid_ns)
            print(f"  Fallback-Ergebnis: {len(valid_sorted)} gültige N")

    if len(valid_sorted) == 0:
        return []

    if len(valid_sorted) >= count:
        selected = random.sample(valid_sorted, count)
    else:
        print(f" Nur {len(valid_sorted)} verfügbar, aber {count} angefordert → Wiederholen bis Zielmenge.")
        selected = []
        while len(selected) < count:
            selected.extend(valid_sorted)
        selected = selected[:count]

    for idx, n in enumerate(selected, 1):
        print(f"  [{idx}/{count}] ✓ N={n} (bits={n.bit_length()})")

    return selected


def generate_n_values_equal_factor_bits_large(bits, count):
    """
    Für größere target_bits (≥32) erzeugen wir zufällig p und q mit gleicher Bitlänge b
    und akzeptieren nur N=p*q mit EXAKT 'bits'.
    """
    b = choose_equal_factor_bits_for_target_N_bits(bits)
    p_lower, p_upper = bounds_for_bits(b)

    print(f"  Ziel-Bitlänge N: {bits} Bit")
    print(f"  Faktor-Bitlänge: p, q = {b} Bit (gleich)")
    print(f"  Strategie: Zufallsgenerierung mit Validierung")
    print(f"  Bereiche: p,q ∈ [{p_lower}, {p_upper}]")

    products = []
    attempts = 0
    max_attempts = count * 200000  # großzügig, weil wir streng validieren
    rejected = 0

    while len(products) < count and attempts < max_attempts:
        attempts += 1
        try:
            p = generate_prime_within_range(p_lower, p_upper)
            q = generate_prime_within_range(p_lower, p_upper)
        except ValueError:
            continue

        # Sicherstellen, dass p,q wirklich gleiche Bitlänge haben
        if p.bit_length() != b or q.bit_length() != b:
            rejected += 1
            if rejected <= 3:
                print(f"    p/q Bitlänge abweichend: p_bits={p.bit_length()}, q_bits={q.bit_length()}")
            continue

        n = p * q
        is_ok, actual_bits, err = validate_bitlength(n, bits)
        if not is_ok:
            rejected += 1
            if rejected <= 5:
                print(f"    Abgelehnt: N={n} (bits={actual_bits}) → {err}")
            continue

        if n in products:
            continue

        products.append(n)
        print(f"  [{len(products)}/{count}] ✓ N={n} (p_bits=q_bits={b}, N_bits={actual_bits})")

    if len(products) < count:
        print(f"  Warnung: Nur {len(products)}/{count} Zahlen nach {attempts} Versuchen erzeugt.")
    return products


def generate_n_values_equal_factor_bits(bits, count):
    """
    Öffentliche API: Erzeugt N=p*q mit EXAKTER Bitlänge 'bits',
    wobei p und q IMMER dieselbe Bitlänge haben.
    Nutzt je nach Größe Enumeration oder Zufallserzeugung.
    """
    if bits <= 28:
        return generate_n_values_equal_factor_bits_small(bits, count)
    else:
        return generate_n_values_equal_factor_bits_large(bits, count)


# ------------------------------
# Batch über viele Bitlängen
# ------------------------------

def generate_all_bitlengths(output_dir="n_values_", numbers_per_bitlength=25):
    """
    Generiert N-Werte für Bitlängen 8..100 (Schritt 4),
    mit der Nebenbedingung: p und q haben IMMER die gleiche Bitlänge.
    Alle N werden streng auf die Ziel-Bitlänge validiert.
    """
    bit_lengths = list(range(8, 101, 4))  # 8,12,16,...,96,100

    print("=" * 72)
    print("N-Generator (p,q gleich-bittig) für Pollard-Rho Experimente")
    print("Strikte Bitlängen-Validierung für N")
    print("=" * 72)
    print(f"Bitlängen: {bit_lengths}")
    print(f"Zahlen pro Bitlänge: {numbers_per_bitlength}")
    print(f"Ausgabeverzeichnis: {output_dir}/")
    print("=" * 72)

    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    master_file = os.path.join(output_dir, f"all_n_equal_bits_{timestamp}.txt")
    master_list = []

    total_generated = 0
    total_rejected = 0
    start_time = datetime.now()

    for bits in bit_lengths:
        print("\n" + "=" * 72)
        print(f"Bitlänge: {bits} Bit")
        print("=" * 72)

        n_values = generate_n_values_equal_factor_bits(bits, numbers_per_bitlength)

        print("\n  Finale Validierung...")
        validated = []
        for n in n_values:
            ok, actual_bits, err = validate_bitlength(n, bits)
            if ok:
                validated.append(n)
            else:
                print(f"    ✗ VERWORFEN: N={n} hat {actual_bits} Bit statt {bits} → {err}")
                total_rejected += 1

        # Speichern
        filename = os.path.join(output_dir, f"n_values_{bits:03d}bit.txt")
        with open(filename, "w") as f:
            for n in validated:
                if n.bit_length() == bits:
                    f.write(f"{n}\n")
                else:
                    print(f"    ✗ KRITISCH: N={n} beim Schreiben verworfen (bits={n.bit_length()})")

        print(f"✓ {len(validated)} Werte gespeichert in: {filename}")
        master_list.extend(validated)
        total_generated += len(validated)

    # Masterdatei
    with open(master_file, "w") as f:
        for n in master_list:
            f.write(f"{n}\n")

    duration = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 72)
    print("FERTIG")
    print("=" * 72)
    print(f"Gesamt generiert: {total_generated}")
    print(f"Abgelehnt in finaler Prüfung: {total_rejected}")
    print(f"Dauer: {duration:.1f} s")
    print("Ausgabedateien:")
    print(f"  - Master: {master_file}")
    print(f"  - Pro Bitlänge: {output_dir}/n_values_equal_XXXbit.txt")
    print("\nNächster Schritt:")
    print(f"  python3 pollardrhov3.py {master_file} results.csv --repeats 3")
    print("=" * 72)

    return master_file, output_dir


# ------------------------------
# CLI
# ------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Erzeugt Semiprimes N=p*q mit EXAKTER N-Bitlänge, wobei p und q IMMER die gleiche Bitlänge haben."
    )
    parser.add_argument(
        "--output-dir", type=str, default="n_values_equal",
        help="Ausgabeverzeichnis (default: n_values_equal)"
    )
    parser.add_argument(
        "--count", type=int, default=25,
        help="Anzahl N-Werte pro Bitlänge (default: 25)"
    )
    args = parser.parse_args()

    generate_all_bitlengths(output_dir=args.output_dir, numbers_per_bitlength=args.count)


if __name__ == "__main__":
    main()