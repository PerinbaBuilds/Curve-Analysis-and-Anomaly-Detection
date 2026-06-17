# Software Requirements Specification

## Exploratory Data Analysis on Launch Vehicle Telemetry Data

| | |
|---|---|
| Document version | 1.0 |
| Status | Baseline (derived from current implementation) |
| Repository | Curve-Analysis-and-Anomaly-Detetction |

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for the
Launch Vehicle Telemetry Curve Analysis and Anomaly Detection application. It is
intended for developers, reviewers, and future maintainers who need an
unambiguous description of what the system does, the data it operates on, and
the constraints it operates under.

### 1.2 Document Conventions

- Requirements are identified as `FR-<n>` (functional) and `NFR-<n>`
  (non-functional) and may be referenced from the Software Design Document
  (`docs/SDD.md`).
- **Status: Implemented** — the requirement is satisfied by code present in the
  repository today.
- **Status: Planned** — the requirement is described in project documentation
  / vision (e.g. the README feature list) but is not yet present in the
  current codebase. These are included so the gap is tracked explicitly
  rather than silently dropped.
- Priority is rated **High / Medium / Low**.

### 1.3 Intended Audience and Reading Suggestions

- **Developers / maintainers** — read Sections 3-6 alongside `docs/SDD.md`.
- **Reviewers / academic evaluators** — Sections 1, 2, and 3 give a complete
  functional picture without needing to read source code.
- **Operators running the tool** — Section 4 (interfaces) and the root
  `README.md` cover setup and usage.

### 1.4 Project Scope

The system is a desktop tool for post-flight (offline) analysis of launch
vehicle telemetry. It lets an analyst:

1. Load time-series telemetry for a given vehicle/mission/parameter from a
   local SQLite database.
2. Compare the telemetry curve against nominal/upper/lower reference bounds
   and quantify deviation.
3. Run unsupervised anomaly detection over the same telemetry using one of
   three selectable algorithms, with severity classification.

The system does **not** ingest live/real-time telemetry, does not provide
multi-user access control, and does not run as a network service — it is a
single-user, single-machine, file-based desktop tool. These exclusions are
intentional (see Section 2.4) and several are listed as future work in the
README.

### 1.5 Definitions, Acronyms, and Abbreviations

| Term | Meaning |
|---|---|
| Telemetry | Time-stamped sensor/parameter readings transmitted from a launch vehicle |
| Bound | A reference curve (nominal, upper, or lower) that valid telemetry is expected to track |
| Violation | A telemetry sample that falls above the upper bound or below the lower bound at its (interpolated) timestamp |
| Anomaly | A telemetry sample flagged as statistically abnormal by a detection algorithm |
| MSE / RMSE / MAE | Mean Squared / Root-Mean-Squared / Mean Absolute Error, computed against the nominal bound |
| `.dat` file | Whitespace-delimited input file with columns `index, time, value, validity`, used to seed bounds or raw telemetry |
| SDSC-SHAR | Satish Dhawan Space Centre, Sriharikota — ISRO launch range where this project originated |

### 1.6 References

- `README.md` — feature overview, usage workflow, technology stack
- `docs/SDD.md` — Software Design Document (architecture and component design)
- Source files: `database_creation.py`, `database_insertion.py`,
  `curve_analysis.py`, `anomaly_detection.py`

---

## 2. Overall Description

### 2.1 Product Perspective

The product is a standalone, self-contained desktop application built from
four independent Python scripts sharing one SQLite database file
(`database.db`). There is no client-server split and no external service
dependency at runtime. It was developed during an academic internship at
SDSC-SHAR, ISRO, to reduce manual effort in mission telemetry review.

### 2.2 Product Functions

At a high level, the system provides:

- One-time database schema creation (`database_creation.py`).
- Bulk ingestion of telemetry `.dat` files from a fixed folder convention into
  the database (`database_insertion.py`).
- Interactive curve plotting against reference bounds, bound-violation
  detection, and deviation-metric reporting (`curve_analysis.py`).
- Interactive, algorithm-selectable anomaly detection with severity
  classification and CSV export (`anomaly_detection.py`).

### 2.3 User Classes and Characteristics

| User class | Description | Technical level |
|---|---|---|
| Telemetry analyst | Primary user; selects vehicle/mission/parameter, reviews plots and anomaly tables | Domain expert, not necessarily a programmer |
| Data engineer / maintainer | Runs ingestion scripts, manages the SQLite file and `.dat` source data | Technical |

### 2.4 Operating Environment

- **OS:** Originally developed on Windows 10; Tkinter and all dependencies
  are cross-platform (Windows, Linux, macOS), with the caveat in NFR-4.
- **Runtime:** Python 3.8+ (project originally built and tested on 3.8.5;
  the provided `Dockerfile` uses 3.11 for a currently-maintained baseline).
- **Display:** Requires a graphical display (local desktop session, or an
  X11-forwarded display when run in a container — see Section 4.2).
- **Storage:** A local SQLite file (`database.db`) in the working directory;
  no database server required.

### 2.5 Design and Implementation Constraints

- GUI is built with Tkinter (`tkinter.ttk` widgets), and plotting uses
  Matplotlib's `TkAgg` backend embedded via `FigureCanvasTkAgg` — both tie the
  application to a system with Tk and a display available.
- Persistence is SQLite accessed through Python's built-in `sqlite3` module;
  there is no ORM and no migration tooling.
- `curve_analysis.py` and `anomaly_detection.py` are independent entry points,
  each opening its own `sqlite3` connection and running its own
  `tk.Tk().mainloop()`; they are not designed to run in the same process.
- All SQL is parameterized (`?` placeholders) rather than string-formatted,
  which avoids SQL injection from user-supplied dropdown values or file
  contents.

### 2.6 Assumptions and Dependencies

- The SQLite database file is named `database.db` and located in the current
  working directory when any of the four scripts are launched.
- Source telemetry `.dat` files for bulk ingestion live under
  `~/Desktop/rocket_data/<vehicle>_<mission>/<parameter>.dat`, one
  subfolder per vehicle+mission combination (folder name split on the first
  underscore).
- `.dat` files (both bulk-ingestion and bounds-upload) are whitespace
  delimited with exactly four columns: `index`, `time`, `value`, `validity`.
- Required third-party packages (`pandas`, `numpy`, `matplotlib`,
  `scikit-learn`, `scipy`) are installed; see `requirements.txt`.

---

## 3. System Features (Functional Requirements)

### 3.1 FR-1: Database Schema Initialization
**Status:** Implemented · **Priority:** High

The system shall create, on demand, a SQLite schema consisting of six tables:
`vehicle`, `mission`, `parameter`, `telemetry_data`, `parameter_bounds`, and
the foreign-key relationships between them, plus a composite index
`idx_mission_param_time` on `telemetry_data(mission_id, parameter_id, time)`
to accelerate the query pattern used by every other component.

*Source:* `database_creation.py`

### 3.2 FR-2: Bulk Telemetry Ingestion
**Status:** Implemented · **Priority:** High

The system shall scan a fixed root folder for subfolders named
`<vehicle>_<mission>`, parse the vehicle and mission identifiers from the
folder name, treat each `.dat` file inside as one telemetry parameter (named
from the filename), and insert all rows into `telemetry_data`, creating
`vehicle`/`mission`/`parameter` records as needed (get-or-create semantics).
Duplicate primary keys (same mission, parameter, and time) shall be silently
ignored (`INSERT OR IGNORE`) rather than raising an error.

*Source:* `database_insertion.py`

### 3.3 FR-3: Vehicle / Mission / Parameter Selection
**Status:** Implemented · **Priority:** High

The system shall let the user pick a vehicle, then dynamically populate the
mission list for that vehicle, then dynamically populate the parameter list
for that mission, all sourced live from the database (no hardcoded lists).
This behavior shall be identical in both `curve_analysis.py` and
`anomaly_detection.py`.

### 3.4 FR-4: Reference Bounds Management
**Status:** Implemented · **Priority:** High

Before plotting a curve, the system shall check whether `nominal`, `upper`,
and `lower` bound series already exist in `parameter_bounds` for the selected
mission/parameter. If any are missing, the system shall prompt the user to
supply one `.dat` file per missing bound type via a file-selection dialog,
validate that each file has exactly four columns, replace any existing bound
rows for that mission/parameter (delete-then-insert), and skip individual
rows whose `value` is null/NaN.

*Source:* `curve_analysis.py` — `check_bounds_existence`,
`get_bounds_files_dialog`, `read_dat_file`, `insert_bounds_from_files`

### 3.5 FR-5: Curve Plotting
**Status:** Implemented · **Priority:** High

The system shall plot the selected telemetry parameter's valid samples
(`validity == 1`) as a time-series line, overlaid with the nominal (orange,
dashed), upper (red, dashed), and lower (green, dashed) bound curves on the
same axes, with a legend, grid, and title identifying vehicle/mission/parameter.

### 3.6 FR-6: Bound Violation Detection
**Status:** Implemented · **Priority:** High

The system shall linearly interpolate the upper and lower bound series
(`scipy.interpolate.interp1d`, with extrapolation) onto the telemetry's own
timestamps, flag samples above the interpolated upper bound or below the
interpolated lower bound as violations, mark them on the plot with distinct
scatter markers, and list them in a dedicated, filterable table (filter
choices: All / Above Upper / Below Lower) with running counts of each type.

### 3.7 FR-7: Deviation Metrics
**Status:** Implemented · **Priority:** Medium

The system shall compute, for every plotted curve, the error between actual
value and the interpolated nominal bound, and report: Mean Squared Error
(MSE), Root Mean Squared Error (RMSE), Mean Absolute Error (MAE), Maximum
Absolute Error, and Euclidean Distance (L2 norm) of the error vector. It
shall also display a plain-language verdict ("well within bounds" vs.
"significant deviation detected") using a fixed maximum-absolute-error
threshold of 5.

### 3.8 FR-8: Manual Axis Range Override
**Status:** Implemented · **Priority:** Low

The system shall auto-compute padded X/Y axis limits from the plotted data by
default, but shall allow the user to override any of Xmin/Xmax/Ymin/Ymax via
text entry fields, validating that min < max before applying them.

### 3.9 FR-9: Anomaly Detection Algorithms
**Status:** Implemented · **Priority:** High

The system shall detect anomalies in the selected telemetry parameter's
values using a user-selected algorithm, after standardizing values with
`StandardScaler`:

| Algorithm | Configurable parameter | Default |
|---|---|---|
| Z-Score | Threshold (\|Z\| above which a point is anomalous) | 3.0 |
| Isolation Forest | Contamination fraction | 0.05 |
| One-Class SVM | `nu` | 0.05 |

The system shall report the resulting anomaly rate as a percentage of points
flagged, and a one-line plain-language summary of the algorithm and its
configured parameter.

### 3.10 FR-10: Severity Classification
**Status:** Implemented · **Priority:** Medium

For every point flagged as anomalous, the system shall classify severity
based on the point's deviation from the dataset mean, in units of standard
deviation: **Critical** (> 3σ), **High** (> 2σ), **Warning** (≤ 2σ but still
flagged anomalous by the model). Each severity shall be rendered with a
distinct marker/color on the plot (Critical: red X, High: orange diamond,
Warning: yellow circle).

### 3.11 FR-11: Anomaly Table, Filtering, and CSV Export
**Status:** Implemented · **Priority:** Medium

The system shall list every detected anomaly (time, value, severity) in a
scrollable table, support filtering the table by severity (All / Critical /
High / Warning), and automatically export all detected anomalies for a run to
a CSV file named `anomalies_<vehicle>_<mission>_<parameter>_<algorithm>_<unix
timestamp>.csv` in the working directory whenever at least one anomaly is
found.

### 3.12 FR-12: Multi-Parameter / Multi-Vehicle Comparison
**Status:** Planned (described in `README.md`, not present in current code)
**Priority:** Medium

The system is intended to allow overlaying multiple parameters from the same
vehicle, and comparing the same parameter across different vehicles/missions,
on a single plot. The current `curve_analysis.py` only renders one
vehicle/mission/parameter combination per plot call (each call clears the
axes). This is tracked as a gap, not a regression, since it was never
implemented.

### 3.13 FR-13: Heatmap Visualization
**Status:** Planned (described in `README.md`, not present in current code)
**Priority:** Low

The system is intended to provide a heatmap view of anomaly concentration
across time and severity. No heatmap-generation code exists in
`anomaly_detection.py` today.

---

## 4. External Interface Requirements

### 4.1 User Interfaces

Two independent Tkinter windows, each with:

- A top control bar of dropdowns (vehicle, mission, parameter, [algorithm])
  that populate dynamically and cascade (vehicle → mission → parameter).
- A central Matplotlib canvas with the standard navigation toolbar (zoom,
  pan, save) embedded via `NavigationToolbar2Tk`.
- A right-hand info panel with computed metrics/summary text and a
  scrollable, filterable results table (`ttk.Treeview`).

See `docs/SDD.md` Section 7 for the full widget layout.

### 4.2 Hardware Interfaces

None beyond a standard display, keyboard, and mouse. No telemetry hardware,
sensors, or network links are read directly — all data arrives via files or
the SQLite database.

### 4.3 Software Interfaces

| Interface | Direction | Format |
|---|---|---|
| SQLite database (`database.db`) | Read/Write | Tables per Section 6 |
| Bounds upload dialog | Input | `.dat`, whitespace-delimited, 4 columns |
| Bulk ingestion source folder | Input | `.dat`, whitespace-delimited, 4 columns |
| Anomaly export | Output | `.csv`, columns: Time, Value, Anomaly, Severity |

When containerized, the application also requires an X11 display socket
forwarded from the host (see `docker-compose.yml`); this is a deployment-time
interface, not a network protocol the application implements itself.

### 4.4 Data Interfaces — `.dat` File Format

Whitespace-delimited (one or more spaces/tabs), no header row, exactly four
columns in this order:

```
index   time    value   validity
0       0.0     12.34   1
1       0.1     12.40   1
...
```

`validity` of `1` marks a sample as usable; `curve_analysis.py` filters
telemetry to `validity == 1` before plotting and metric computation (the
bulk-ingestion path in `database_insertion.py` stores the column as-is
without filtering at insert time).

---

## 5. Non-Functional Requirements

### NFR-1: Performance
**Priority:** Medium

Telemetry for a single mission/parameter is loaded fully into memory as a
Pandas DataFrame; the composite index on `telemetry_data` keeps single-series
lookups efficient for typical single-mission telemetry volumes. The system is
not designed or tested for streaming or multi-gigabyte single-series
datasets.

### NFR-2: Reliability / Error Handling
**Priority:** Medium

User-facing errors (missing selection, missing data, bad file format,
invalid axis range, database errors) shall be surfaced via `messagebox`
dialogs rather than uncaught exceptions. Diagnostic detail beyond the
dialog text is currently written to stdout via `print()` rather than a
structured logging framework (see `docs/SDD.md` Section 8 for the
consolidation opportunity this presents).

### NFR-3: Usability
**Priority:** Medium

Dropdowns must cascade automatically (selecting a vehicle repopulates
missions; selecting a mission repopulates parameters) so a user is never
shown a stale or invalid combination. Default values are pre-filled for all
algorithm parameters (Z-score threshold, contamination, nu) so detection can
be run with a single click without prior configuration.

### NFR-4: Portability
**Priority:** Medium

The application must run on any OS with Python 3.8+ and Tk available. On
Debian/Ubuntu-based Linux (including the provided Docker image), Tkinter
requires the separate `python3-tk` OS package since it is not distributed via
pip. The GUI itself additionally requires a reachable display (native on
Windows/macOS desktops; X11 forwarding when containerized).

### NFR-5: Security
**Priority:** Medium

All database queries across all four scripts use parameterized SQL (`?`
placeholders); no string-interpolated SQL is present. There is no
authentication or authorization layer — this is consistent with the system's
scope as a single-user local desktop tool, not a network-exposed service.

### NFR-6: Maintainability
**Priority:** Low

The codebase currently has no automated test suite. `requirements.txt` is
intended to pin the minimum compatible set of third-party dependencies to
keep environments reproducible across machines and the Docker image.

---

## 6. Data Requirements

| Table | Key columns | Purpose |
|---|---|---|
| `vehicle` | `veh_id` (PK) | Launch vehicle catalog (name, height, weight, payload type) |
| `mission` | `mission_id` (PK), `veh_id` (FK) | Missions flown on a given vehicle |
| `parameter` | `parameter_id` (PK) | Catalog of telemetry parameter names |
| `telemetry_data` | PK (`mission_id`, `parameter_id`, `time`) | Time-series readings: `idx`, `time`, `value`, `validity` |
| `parameter_bounds` | PK (`mission_id`, `parameter_id`, `bound_type`, `idx`) | Nominal/upper/lower reference series per mission+parameter |

Full column definitions and constraints are documented in
`docs/SDD.md` Section 4 (Data Design), generated from the live DDL in
`database_creation.py`.

---

## Appendix A: Known Issues / Open Items

These are tracked here rather than silently fixed, since they affect how
requirements should be read against the current code:

1. Earlier README revisions referred to the database file as `sds1.db`;
   every script actually opens `database.db`. The README has been corrected
   to match the code.
2. `anomaly_detection.py` does not filter on the `validity` column before
   running detection, while `curve_analysis.py` filters to `validity == 1`
   before plotting/metrics. Whether this divergence is intentional is open.
3. FR-12 (multi-parameter/vehicle comparison) and FR-13 (heatmap) are
   described as features in the README but are not implemented in the
   current codebase (see Sections 3.12-3.13).

## Appendix B: Requirement-to-Source Traceability

| Requirement | Primary source file |
|---|---|
| FR-1 | `database_creation.py` |
| FR-2 | `database_insertion.py` |
| FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 | `curve_analysis.py` |
| FR-9, FR-10, FR-11 | `anomaly_detection.py` |
| FR-12, FR-13 | Not yet implemented |
