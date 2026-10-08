"""Download the BPI Challenge 2020 "Domestic Declarations" event log and turn it into a flat CSV.

The log is real public research data (Eindhoven University of Technology, CC BY-NC 4.0).
It is NOT committed to git: run `python -m opportunity_assessment.eventlog` once to fetch it.

    python -m opportunity_assessment.eventlog                 # download from 4TU.ResearchData + convert
    python -m opportunity_assessment.eventlog --xes FILE      # convert a file you downloaded yourself
                                                              # (.xes, .xes.gz or .zip)

The CSV has one row per event: case_id, activity, timestamp (UTC), role, resource, amount.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

from .config import RAW_DIR

DATASET_PAGE = "https://data.4tu.nl/datasets/6a0a26d2-82d0-4018-b1cd-89afb0e8627f"
DOWNLOAD_URL = (
    "https://data.4tu.nl/file/6a0a26d2-82d0-4018-b1cd-89afb0e8627f/6eeb0328-f991-48c7-95f2-35033504036e"
)
OFFICIAL_MD5 = "6a78c39491498363ce4788e0e8ca75ef"  # MD5 of DomesticDeclarations.xes.gz published by 4TU
EXPECTED_CASES = 10_500
EXPECTED_EVENTS = 56_437
LOG_CSV = RAW_DIR / "domestic_declarations.csv"


def download(target: Path = RAW_DIR / "DomesticDeclarations.xes.gz") -> Path:
    """Download the official file and check its MD5, so we know it is the published version."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(DOWNLOAD_URL, timeout=120) as response:  # noqa: S310 (fixed https URL)
        content = response.read()
    digest = hashlib.md5(content).hexdigest()
    if digest != OFFICIAL_MD5:
        raise RuntimeError(
            f"Downloaded file has MD5 {digest}, expected {OFFICIAL_MD5}. The site may be down "
            f"(4TU sometimes answers with a maintenance message). Download it by hand from {DATASET_PAGE} "
            "and run: python -m opportunity_assessment.eventlog --xes <file>"
        )
    target.write_bytes(content)
    return target


def read_xes_bytes(path: Path) -> bytes:
    """Return the XML text of an .xes, .xes.gz or .zip (containing one .xes) file."""
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":  # gzip magic number
        return gzip.decompress(raw)
    if raw[:2] == b"PK":  # zip magic number
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".xes"))
            return archive.read(name)
    return raw


def parse_xes(xml_bytes: bytes) -> pd.DataFrame:
    """Flatten the XES XML into one row per event. Case attributes (amount) are copied to every event."""
    rows = []
    root = ET.fromstring(xml_bytes)
    for trace in root.iter("trace"):
        case = {child.get("key"): child.get("value") for child in trace if child.tag != "event"}
        for event in trace.iter("event"):
            attrs = {child.get("key"): child.get("value") for child in event}
            rows.append({
                "case_id": case.get("concept:name"),
                "activity": attrs.get("concept:name"),
                "timestamp": attrs.get("time:timestamp"),
                "role": attrs.get("org:role"),
                "resource": attrs.get("org:resource"),
                "amount": float(case.get("Amount", "nan")),
            })
    log = pd.DataFrame(rows)
    # Timestamps carry a +01:00/+02:00 offset; store them in UTC so durations are exact across DST changes.
    log["timestamp"] = pd.to_datetime(log["timestamp"], utc=True)
    return log


def convert(xes_path: Path, csv_path: Path = LOG_CSV) -> pd.DataFrame:
    log = parse_xes(read_xes_bytes(xes_path))
    cases, events = log["case_id"].nunique(), len(log)
    if (cases, events) != (EXPECTED_CASES, EXPECTED_EVENTS):
        print(f"WARNING: expected {EXPECTED_CASES} cases / {EXPECTED_EVENTS} events, got {cases} / {events}")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(csv_path, index=False)
    print(f"Wrote {csv_path} ({cases} cases, {events} events)")
    return log


def load_log(path: Path = LOG_CSV) -> pd.DataFrame:
    """Read an event-log CSV (the real one or a test fixture) with parsed UTC timestamps."""
    if not Path(path).exists():
        raise FileNotFoundError(f"{path} not found. Run: python -m opportunity_assessment.eventlog")
    log = pd.read_csv(path)
    log["timestamp"] = pd.to_datetime(log["timestamp"], utc=True, format="ISO8601")
    return log


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xes", type=Path, help="convert this local file instead of downloading")
    args = parser.parse_args()
    convert(args.xes or download())


if __name__ == "__main__":
    main()
