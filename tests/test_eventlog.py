"""Reading the XES event log (plain, gzip and zip) into one row per event."""

from __future__ import annotations

import gzip
import io
import zipfile

from opportunity_assessment.eventlog import parse_xes, read_xes_bytes

XES = b"""<?xml version="1.0" encoding="UTF-8" ?>
<log xes.version="1.0">
  <trace>
    <string key="concept:name" value="declaration 1"/>
    <float key="Amount" value="26.5"/>
    <event>
      <string key="concept:name" value="Declaration SUBMITTED by EMPLOYEE"/>
      <date key="time:timestamp" value="2017-01-09T09:49:50.000+01:00"/>
      <string key="org:role" value="EMPLOYEE"/>
      <string key="org:resource" value="STAFF MEMBER"/>
    </event>
    <event>
      <string key="concept:name" value="Payment Handled"/>
      <date key="time:timestamp" value="2017-07-01T10:00:00.000+02:00"/>
      <string key="org:role" value="UNDEFINED"/>
      <string key="org:resource" value="SYSTEM"/>
    </event>
  </trace>
</log>"""


def test_parse_flattens_events_and_converts_to_utc():
    log = parse_xes(XES)
    assert list(log["activity"]) == ["Declaration SUBMITTED by EMPLOYEE", "Payment Handled"]
    assert list(log["case_id"]) == ["declaration 1"] * 2
    assert log["amount"].iloc[1] == 26.5
    assert str(log["timestamp"].iloc[0]) == "2017-01-09 08:49:50+00:00"  # +01:00 in winter
    assert str(log["timestamp"].iloc[1]) == "2017-07-01 08:00:00+00:00"  # +02:00 in summer


def test_reads_gzip_zip_and_plain(tmp_path):
    plain = tmp_path / "log.xes"
    plain.write_bytes(XES)
    gz = tmp_path / "log.xes.gz"
    gz.write_bytes(gzip.compress(XES))
    zipped = tmp_path / "log.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("DomesticDeclarations.xes", XES)
    zipped.write_bytes(buffer.getvalue())
    assert read_xes_bytes(plain) == read_xes_bytes(gz) == read_xes_bytes(zipped) == XES
