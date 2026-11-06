"""Download public SCARE showtimes with bounded parallelism."""
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json
import subprocess
import sys
from urllib.parse import urlencode

from import_seances import POSTAL_RANGES, REQUIRED

ENDPOINT = "https://datacinesindes.fr/data-fair/api/v1/datasets/programmation-cinemas/lines"
LIMIT = 10_000


def request(first, last, **options):
    query = urlencode({"draft": "false", "qs": f"cinecp:[{first:05} TO {last:05}]", **options})
    return subprocess.check_output([
        "curl", "--fail", "--silent", "--show-error", "--location",
        "--retry", "2", "--max-time", "45", ENDPOINT + "?" + query,
    ]).decode("utf-8-sig")


def download(first, last):
    content = request(first, last, size=LIMIT, page=1, format="csv", sep=",")
    reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
    if not reader.fieldnames:
        if json.loads(request(first, last, size=1, format="json")).get("total") == 0:
            return []
    if not REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError(f"{first:05}–{last:05} : en-tête CSV inattendu.")
    rows = list(reader)
    for row in rows:
        postal_code = (row["cinecp"] or "").strip()
        if not postal_code.isdecimal() or not first <= int(postal_code) <= last:
            raise ValueError(f"{first:05}–{last:05} : filtre postal non appliqué.")
    if len(rows) < LIMIT:
        return rows
    if first == last:
        raise ValueError(f"{first:05} : plafond atteint sur un seul code postal.")
    middle = (first + last) // 2
    return download(first, middle) + download(middle + 1, last)


def fetch_range(bounds):
    first, last = bounds
    rows = download(first, last)
    print(f"{first:05}–{last:05} : {len(rows)} lignes.", flush=True)
    return rows


def main():
    with ThreadPoolExecutor(max_workers=4) as pool, open(
        sys.argv[1], "w", encoding="utf-8", newline=""
    ) as output:
        writer = csv.DictWriter(output, fieldnames=sorted(REQUIRED), extrasaction="ignore")
        writer.writeheader()
        for rows in pool.map(fetch_range, POSTAL_RANGES):
            writer.writerows(rows)


if __name__ == "__main__":
    main()
