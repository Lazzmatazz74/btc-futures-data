#!/usr/bin/env python3
"""merge_extra_rev1.py (2026-09-25) - used by the safe-push step of fetch_extra_data_rev4.yml.
Puts this run's freshly downloaded data/extra files back on top of the LATEST main without losing rows that
another run pushed in the meantime.
  * CSV present on both sides: rows are unioned by their first column (timestamp key); where both sides have
    the same key, THIS run's row wins (it is the newer download). If the first column is not unique within a
    file, whole lines are unioned instead. Header = this run's header. Rows sorted by key.
  * Any other file (status.json, ...): this run's copy wins.
  * Files that exist only on main are left untouched.
Usage: python merge_extra_rev1.py <saved_dir> <target_dir>"""
import csv, io, os, shutil, sys


def key_sort(k):
    try: return (0, float(k))
    except ValueError: return (1, k)


def merge_csv(ours_path, theirs_path, out_path):
    with open(ours_path, newline="") as f: ours = f.read().splitlines()
    with open(theirs_path, newline="") as f: theirs = f.read().splitlines()
    if not ours: return                                  # nothing downloaded this run -> keep main's file
    header, o_rows = ours[0], [r for r in ours[1:] if r.strip()]
    t_rows = [r for r in theirs[1:] if r.strip()] if theirs and theirs[0] == header else []
    first = lambda line: next(csv.reader(io.StringIO(line)))[0]
    o_keys = [first(r) for r in o_rows]
    if len(set(o_keys)) == len(o_keys):
        rows = {first(r): r for r in t_rows}
        rows.update(zip(o_keys, o_rows))
        body = [rows[k] for k in sorted(rows, key=key_sort)]
    else:
        seen, body = set(), []
        for r in t_rows + o_rows:
            if r not in seen: seen.add(r); body.append(r)
        body.sort(key=lambda r: key_sort(first(r)))
    with open(out_path, "w", newline="") as f: f.write("\n".join([header] + body) + "\n")


def main(saved, target):
    n = 0
    for root, _, files in os.walk(saved):
        for name in files:
            src = os.path.join(root, name); rel = os.path.relpath(src, saved); dst = os.path.join(target, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if name.endswith(".csv") and os.path.exists(dst): merge_csv(src, dst, dst)
            else: shutil.copy2(src, dst)
            n += 1
    print(f"merged {n} file(s) from {saved} into {target}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
