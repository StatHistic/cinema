"""Build the Pages index from the public SCARE CSV."""
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

# Postal ranges: 20 covers both Corsican departments.
POSTAL_RANGES = tuple((n * 1000, n * 1000 + 999) for n in range(1, 96)) + tuple(
    (n * 100, n * 100 + 99) for n in (971, 972, 973, 974, 976)
)
REQUIRED = {"cinecp", "cinenom", "showstart", "filmtitle", "_coords.lat",
            "_coords.lon", "showurl", "filmversion"}
PARIS = ZoneInfo("Europe/Paris")


def read_shows(path, now):
    shows = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError("Colonnes manquantes dans l’export SCARE.")
        for row in reader:
            postal_code = (row["cinecp"] or "").strip()
            if len(postal_code) != 5 or not postal_code.isascii() or not postal_code.isdecimal():
                continue
            if not any(first <= int(postal_code) <= last for first, last in POSTAL_RANGES):
                continue
            if not all(row[key] for key in REQUIRED - {"showurl", "filmversion", "_coords.lat", "_coords.lon"}):
                continue
            start = datetime.fromisoformat(row["showstart"])
            if start.tzinfo is None:
                raise ValueError("Fuseau horaire absent de l’export SCARE.")
            if start <= now:
                continue
            local = start.astimezone(PARIS)
            try:
                lat, lon = float(row["_coords.lat"]), float(row["_coords.lon"])
                if not all(map(math.isfinite, (lat, lon))) or abs(lat) > 90 or abs(lon) > 180:
                    lat, lon = None, None
            except (ValueError, TypeError):
                lat, lon = None, None
            # Acceslibre, Le Gallia, Saintes. Licence Ouverte 2.0.
            # Source fiche mise à jour le 2023-07-04, consultée le 2026-11-07.
            if lat is None and row["cinenom"].strip().casefold() == "gallia" and postal_code in {"17100", "17104"}:
                lat, lon = 45.74716241741378, -0.6345596909523011
            version = {"VERSION_ORIGINAL": "VO", "VERSION_FRANCAISE": "VF"}.get(row["filmversion"], "")
            shows.add((local.date().isoformat(), local.strftime("%H:%M"), row["filmtitle"].strip(),
                       row["cinenom"], lat, lon, row["showurl"] or "", version))
    if not shows:
        raise ValueError("Aucune séance à venir pour les salles suivies.")
    return sorted(shows, key=lambda show: tuple(str(value) for value in show))


def main():
    source, template, target = map(Path, sys.argv[1:])
    now = datetime.now(timezone.utc)
    shows = read_shows(source, now)
    payload = json.dumps(shows, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    page, count = re.subn(
        r'(<script id="data" type="application/json">).*?(</script>)',
        lambda match: match[1] + payload + match[2],
        template.read_text(encoding="utf-8"), flags=re.S,
    )
    marker = 'data-imported-at=""'
    if count != 1 or page.count(marker) != 1:
        raise ValueError("Le modèle HTML ne contient pas les repères d’import attendus.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page.replace(marker, f'data-imported-at="{now.isoformat()}"'), encoding="utf-8")
    print(f"{len(shows)} séances exportées.")


if __name__ == "__main__":
    main()
