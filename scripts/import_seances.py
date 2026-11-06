"""Build the Pages index from the public SCARE CSV."""
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

DEPARTMENTS = ("75", "77", "78", "91", "92", "93", "94", "95")
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
            if (row["cinecp"] or "").strip()[:2] not in DEPARTMENTS:
                continue
            if not all(row[key] for key in REQUIRED - {"showurl", "filmversion"}):
                continue
            start = datetime.fromisoformat(row["showstart"])
            if start.tzinfo is None:
                raise ValueError("Fuseau horaire absent de l’export SCARE.")
            if start <= now:
                continue
            local = start.astimezone(PARIS)
            lat, lon = float(row["_coords.lat"]), float(row["_coords.lon"])
            if not all(map(math.isfinite, (lat, lon))) or abs(lat) > 90 or abs(lon) > 180:
                raise ValueError("Coordonnées invalides dans l’export SCARE.")
            version = {"VERSION_ORIGINAL": "VO", "VERSION_FRANCAISE": "VF"}.get(row["filmversion"], "")
            shows.add((local.date().isoformat(), local.strftime("%H:%M"), row["filmtitle"].strip(),
                       row["cinenom"], lat, lon, row["showurl"] or "", version))
    if not shows:
        raise ValueError("Aucune séance à venir pour les salles suivies.")
    return sorted(shows)


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
