# LaneQA

LaneQA is a Streamlit dashboard for validating lane-level map data. It supports a simple JSON lane format and an OpenDRIVE-lite importer for `.xodr` files, then surfaces geometry and topology issues through metrics, an interactive map view, an issue table, and a downloadable QA report.

The project focuses on practical HD map quality checks that can be reviewed without a database, authentication layer, simulator, or separate backend service.

## Features

- Upload LaneQA JSON, OpenDRIVE `.xodr`, or OpenDRIVE XML files
- Validate lane identifiers, coordinate records, minimum geometry, and sharp turns
- Parse OpenDRIVE road, lane section, lane, width, predecessor, and successor metadata
- Flag missing lane widths, broken lane links, isolated drivable lanes, and duplicate lane identities
- Visualize valid and invalid lanes with Plotly
- Export a structured `qa_report.json`

## Tech Stack

- Python
- Streamlit
- Pandas
- NumPy
- Plotly
- `xml.etree.ElementTree` for OpenDRIVE-lite parsing

## Project Structure

```text
LaneQA/
  app.py
  validators.py
  visualization.py
  importers/
    opendrive.py
  sample_data/
    lanes_sample.json
  samples/
    opendrive/
      broken_successor_minimal.xodr
  tests/
    test_opendrive_importer.py
  requirements.txt
```

## LaneQA JSON Format

```json
[
  {
    "lane_id": "L1",
    "points": [[0, 0], [10, 0], [20, 1]],
    "speed_limit": 35
  }
]
```

## Validation Logic

For JSON inputs, LaneQA checks:

- Missing or empty lane IDs
- Duplicate lane IDs
- Fewer than two valid coordinate points
- Malformed, null, or non-numeric coordinates
- Sharp turn anomalies

Sharp turns are calculated over every three consecutive points. For points `A`, `B`, and `C`, the app computes vectors `AB` and `BC`, then uses the dot product formula:

```text
cos(theta) = (AB dot BC) / (|AB| * |BC|)
```

The resulting angle is compared with the dashboard threshold. Zero-length vectors are skipped because they do not produce a meaningful angle.

## OpenDRIVE-lite Import

The OpenDRIVE-lite importer reads `.xodr` files directly with Python's standard XML parser. It extracts:

- Header metadata
- Road ID, name, length, and junction ID
- Lane section `s` values
- Left, center, and right lane groups
- Lane ID, type, and level
- Lane width polynomial attributes: `sOffset`, `a`, `b`, `c`, `d`
- Predecessor and successor lane links

This importer does not evaluate full OpenDRIVE road geometry. Parsed lanes are normalized into LaneQA records with approximate display coordinates so metadata and topology checks can be reviewed in the dashboard.

## CARLA OpenDRIVE Files

Public CARLA OpenDRIVE maps can be tested without installing CARLA:

```bash
mkdir -p samples/opendrive/carla
curl -L -o samples/opendrive/carla/Town01.xodr \
  https://raw.githubusercontent.com/carla-simulator/opendrive-test-files/master/Town01.xodr
curl -L -o samples/opendrive/carla/Town04.xodr \
  https://raw.githubusercontent.com/carla-simulator/opendrive-test-files/master/Town04.xodr
```

Use `Town01.xodr` for a standard demo and `Town04.xodr` for a larger input. The included `samples/opendrive/broken_successor_minimal.xodr` fixture is intentionally invalid and should produce a broken successor issue.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
pip install pytest
pytest
```

## Deploy

On Streamlit Community Cloud, set the app entry point to:

```text
app.py
```

The deployment will install packages from `requirements.txt`.

## Scope

LaneQA is designed as a focused QA dashboard, not a full HD map platform. It does not include persistence, user accounts, CARLA runtime integration, ROS integration, Autoware integration, or complete OpenDRIVE geometry evaluation.
