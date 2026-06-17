# Software Design Document

## Exploratory Data Analysis on Launch Vehicle Telemetry Data

| | |
|---|---|
| Document version | 1.0 |
| Companion document | `docs/SRS.md` (requirements this design satisfies) |

---

## 1. Introduction

### 1.1 Purpose

This document describes the technical design of the system: its
architecture, data model, component responsibilities, key algorithms, UI
layout, and deployment model. It is written from the current implementation
(four Python scripts) rather than as an aspirational redesign.

### 1.2 Scope

Covers `database_creation.py`, `database_insertion.py`,
`curve_analysis.py`, and `anomaly_detection.py`, the shared SQLite schema
they operate on, and the container packaging added for deployment
(`Dockerfile`, `docker-compose.yml`).

---

## 2. Architectural Overview

The system is a **script-based, monolithic desktop architecture** — there is
no application server, no API layer, and no background process. Each entry
point is a single Python file that owns its own database connection, its own
Tkinter root window, and its own event loop. Two scripts (`curve_analysis.py`
and `anomaly_detection.py`) are interactive GUI tools; the other two
(`database_creation.py`, `database_insertion.py`) are one-shot batch scripts
run from the command line.

```
                          ┌─────────────────────────┐
                          │       database.db       │
                          │  (SQLite, single file)  │
                          └─────────────────────────┘
                                       ▼
            ┌──────────────────────────┼──────────────────────────┐
            │                          │                          │
┌───────────┴───────────┐  ┌───────────┴───────────┐  ┌───────────┴───────────┐
│ database_creation.py  │  │ database_insertion.py │  │  curve_analysis.py /  │
│     (schema DDL,      │  │  (.dat folder scan,   │  │ anomaly_detection.py  │
│       run once)       │  │    bulk INSERT OR     │  │   (interactive GUI,   │
│                       │  │        IGNORE)        │  │ read + write bounds,  │
│                       │  │                       │  │ read-only telemetry)  │
└───────────────────────┘  └───────────────────────┘  └───────────────────────┘
```

Both GUI tools independently implement the same vehicle → mission →
parameter cascading-dropdown pattern and the same `get_vehicles` /
`get_missions` / `get_parameters` query shape; they are not currently
factored into a shared module. This duplication is noted as technical debt
in Section 10 rather than refactored, since the two tools are still
expected to evolve independently (different control panels, different
result tables).

### 2.2 Process View

| Process | Entry point | Lifetime |
|---|---|---|
| Schema setup | `python database_creation.py` | Runs once, exits immediately |
| Data ingestion | `python database_insertion.py` | Runs once per batch of new `.dat` data, exits when folder scan completes |
| Curve analysis | `python curve_analysis.py` | Long-lived, exits when the Tk window is closed |
| Anomaly detection | `python anomaly_detection.py` | Long-lived, exits when the Tk window is closed |

The two GUI processes are never required to run simultaneously, but they are
safe to run concurrently since SQLite supports multiple readers and each
process opens its own connection; only `curve_analysis.py` writes to the
database at runtime (bounds insertion), and it does so via a short-lived
connection scoped to that single operation.

---

## 3. Data Design

### 3.1 Entity-Relationship Overview

```
vehicle (1) ──< (many) mission (1) ──< (many) telemetry_data
                    │                          ▲
                    │                          │
                    └──< (many) parameter_bounds
                                  ▲
                                  │
parameter (1) ──< (many) telemetry_data
parameter (1) ──< (many) parameter_bounds
```

### 3.2 Table Definitions

**`vehicle`**

| Column | Type | Constraints |
|---|---|---|
| `veh_id` | INTEGER | PK, AUTOINCREMENT |
| `veh_name` | VARCHAR | UNIQUE, NOT NULL |
| `height` | REAL | |
| `weight` | REAL | |
| `payload_type` | VARCHAR | |

**`mission`**

| Column | Type | Constraints |
|---|---|---|
| `mission_id` | INTEGER | PK, AUTOINCREMENT |
| `veh_id` | INTEGER | NOT NULL, FK → `vehicle.veh_id` |
| `mission_name` | VARCHAR | UNIQUE, NOT NULL |
| `launch_date` | DATE | |
| `status` | VARCHAR | |
| `launch_pad` | VARCHAR | |

**`parameter`**

| Column | Type | Constraints |
|---|---|---|
| `parameter_id` | INTEGER | PK, AUTOINCREMENT |
| `parameter_name` | VARCHAR | UNIQUE, NOT NULL |

**`telemetry_data`**

| Column | Type | Constraints |
|---|---|---|
| `mission_id` | INTEGER | NOT NULL, FK → `mission.mission_id`, part of PK |
| `parameter_id` | INTEGER | NOT NULL, FK → `parameter.parameter_id`, part of PK |
| `idx` | INTEGER | NOT NULL (source row index; not part of the PK) |
| `time` | REAL | NOT NULL, part of PK |
| `value` | REAL | |
| `validity` | BOOLEAN | |

Composite index `idx_mission_param_time` on
`(mission_id, parameter_id, time)` mirrors the primary key and exists
explicitly to keep the dominant query path — "all samples for this
mission+parameter, ordered by time" — fast as the table grows; this is the
query used by `fetch_data()` in both GUI tools.

> **Design note:** the primary key is `(mission_id, parameter_id, time)`,
> not `(mission_id, parameter_id, idx)`. Two source rows that share an exact
> timestamp for the same mission/parameter cannot both be stored — the
> second `INSERT OR IGNORE` is dropped silently. This has not caused issues
> with the telemetry sampled so far but is worth knowing before bulk-loading
> a new data source with a different sampling convention.

**`parameter_bounds`**

| Column | Type | Constraints |
|---|---|---|
| `mission_id` | INTEGER | NOT NULL, FK → `mission.mission_id`, part of PK |
| `parameter_id` | INTEGER | NOT NULL, FK → `parameter.parameter_id`, part of PK |
| `bound_type` | TEXT | NOT NULL, `CHECK IN ('upper','lower','nominal')`, part of PK |
| `idx` | INTEGER | NOT NULL, part of PK |
| `time` | DATETIME | NOT NULL |
| `value` | REAL | |
| `validity` | TEXT | |

Unlike `telemetry_data`, this table's PK includes `idx` rather than `time` —
appropriate since bounds are uploaded directly from a `.dat` file and are
replaced wholesale (delete-then-insert) rather than incrementally merged.

### 3.3 File-Based Data Interfaces

**Bulk ingestion source layout** (consumed by `database_insertion.py`):

```
~/Desktop/rocket_data/
└── <vehicle>_<mission>/        e.g. pslv_c59
    ├── <parameter_1>.dat       e.g. acceleration_x.dat
    ├── <parameter_2>.dat
    └── ...
```

The folder name is split on `_` to derive `vehicle` (upper-cased) and
`mission` (the full folder name, lower-cased); each `.dat` filename
(minus extension) becomes a parameter name.

**`.dat` file format** (shared by bulk ingestion and bounds upload):
whitespace-delimited, no header, four columns: `index time value validity`.

**Anomaly export** (`anomaly_detection.py`): CSV with columns
`Time, Value, Anomaly, Severity`, one file per detection run, named
`anomalies_<vehicle>_<mission>_<parameter>_<algorithm>_<unix-timestamp>.csv`.

---

## 4. Component Design

### 4.1 `database_creation.py`

Linear script: opens a connection to `database.db`, issues `CREATE TABLE`
statements for all five tables plus the composite index, commits, and
closes. No functions, no parameters — re-running it against an existing
database will raise "table already exists" errors, so it is meant to be run
exactly once per fresh database file.

### 4.2 `database_insertion.py`

| Function | Responsibility |
|---|---|
| `get_or_create_vehicle(name)` | Look up a vehicle by name; insert with placeholder height/weight/payload if absent. Returns `veh_id`. |
| `get_or_create_mission(name, veh_id)` | Same get-or-create pattern for missions; stamps a placeholder `launch_date`/`status`/`launch_pad`. |
| `get_or_create_parameter(name)` | Same pattern for parameters. |
| Top-level loop | Walks `data_folder`, parses each `<vehicle>_<mission>` subfolder, reads every `.dat` file with `pandas.read_csv(sep=r'\s+')`, and bulk-inserts via `executemany` with `INSERT OR IGNORE`. |

The get-or-create helpers commit immediately after insert so that the
`lastrowid` returned is reliable even though the surrounding loop also
commits per-file.

### 4.3 `curve_analysis.py`

| Function | Responsibility |
|---|---|
| `get_vehicles` / `get_missions` / `get_parameters` | Populate cascading dropdowns from the DB. |
| `fetch_data(mission, parameter)` | Load the full telemetry series for a mission+parameter into a DataFrame (`Index, Time, Value, Validity`). |
| `check_bounds_existence(mission_id, parameter_id)` | Query distinct `bound_type` values already stored for this mission+parameter. |
| `read_dat_file(path)` | Parse a `.dat` file into a 4-column DataFrame; reports parse errors via `messagebox`. |
| `get_bounds_files_dialog()` | Modal `Toplevel` dialog with one file picker per bound type (`upper`/`lower`/`nominal`); validates a file is chosen and is 4-column before allowing confirm. |
| `insert_bounds_from_files(mission_id, parameter_id, files)` | Deletes any existing bound rows for this mission+parameter, then inserts the three uploaded files row-by-row (skipping null/NaN values), inside a transaction with rollback on error. |
| `plot_curve()` | The central orchestration function — see Section 6.1/6.2 for its algorithmic core. |
| `update_violation_table(df)` / `filter_violations()` | Repopulate / filter the `Treeview` of bound violations. |
| `update_missions` / `update_parameters` | Combobox `<<ComboboxSelected>>` callbacks that cascade dropdown contents. |

`plot_curve()` is intentionally a single large function rather than several
smaller ones, since each step (bounds existence check → optional upload →
fetch → interpolate → plot → metrics → table update) depends on the
previous step's result and the function is not reused elsewhere; splitting
it would add indirection without adding reuse.

### 4.4 `anomaly_detection.py`

| Function | Responsibility |
|---|---|
| `get_vehicles` / `get_missions` / `get_parameters` / `fetch_data` | Same role as in `curve_analysis.py`, implemented independently (see Section 2.1 note on duplication). All four wrap their query in a bare `try/except` that returns `[]`/`None` on failure rather than surfacing the error — see Section 8. |
| `calculate_accuracy(y_true, y_pred)` | Computes the fraction of points predicted anomalous. Present in the code but not currently called from `detect_anomalies()` — `anomaly_score` is computed inline instead for each algorithm branch. |
| `classify_severity(values, anomaly_indices)` | Section 6.6. |
| `detect_anomalies()` | Orchestration function: fetch → scale → run selected algorithm → classify severity → plot → update table → export CSV. |
| `update_anomaly_table()` / `filter_table()` | Repopulate / filter the anomaly `Treeview` by severity. |
| `update_missions` / `update_parameters` | Cascading dropdown callbacks (independent implementation from `curve_analysis.py`). |

---

## 5. User Interface Design

### 5.1 `curve_analysis.py` window

```
┌─────────────────────────────────────────────────────────────────────┐
│ Vehicle [▾]  Mission [▾]  Parameter [▾]  Xmin Xmax Ymin Ymax  [Plot] │
├───────────────────────────────────────────┬───────────────────────────┤
│                                             │  📊 Curve Analysis Metrics │
│        Matplotlib canvas                   │  (MSE/RMSE/MAE/MaxErr/    │
│        (telemetry + 3 bound curves +       │   Euclidean)              │
│         violation markers)                 │                           │
│                                             │  📝 Summary verdict       │
│        [Navigation toolbar: zoom/pan/save] │                           │
│                                             │  ⚠️ Bound Violations       │
│                                             │  Filter [▾] [Apply]        │
│                                             │  Treeview: Index/Time/    │
│                                             │  Value/Violation          │
│                                             │  Above Upper: N           │
│                                             │  Below Lower: N           │
└───────────────────────────────────────────┴───────────────────────────┘
```

### 5.2 `anomaly_detection.py` window

```
┌─────────────────────────────────────────────────────────────────────┐
│ Vehicle [▾] Mission [▾] Parameter [▾] Algorithm [▾]   [🔍 Detect]     │
│ Z-Score Threshold [__]  IF Contamination [__]  SVM Nu [__]  Status:.. │
├───────────────────────────────────────────┬───────────────────────────┤
│                                             │  📋 Algorithm Summary     │
│        Matplotlib canvas                   │                           │
│        (series + Critical/High/Warning     │  📊 Detection Statistics  │
│         scatter overlays)                  │  (anomaly rate %)         │
│                                             │                           │
│        [Navigation toolbar]                │  🚨 Anomaly Details        │
│                                             │  Filter by Severity [▾]   │
│                                             │  Treeview: Time/Value/    │
│                                             │  Severity (scrollable)    │
└───────────────────────────────────────────┴───────────────────────────┘
```

Both windows share the same interaction pattern: select inputs top-down,
trigger one primary action button, read results from the right-hand panel.

---

## 6. Algorithm Design

### 6.1 Bound Interpolation

Reference bounds are sampled at their own timestamps, which do not
necessarily align with telemetry timestamps. `scipy.interpolate.interp1d`
(`kind='linear'`, `fill_value='extrapolate'`, `bounds_error=False`) builds a
continuous function from each bound series, which is then evaluated at every
telemetry timestamp. This is only attempted when a bound series has more
than one point; with zero or one point, violation detection is skipped for
that series (treated as "no violations" rather than raising an error).

### 6.2 Violation Detection & Deviation Metrics

```
violation_above[i] = telemetry.value[i] > upper_interp(telemetry.time[i])
violation_below[i] = telemetry.value[i] < lower_interp(telemetry.time[i])

error[i] = telemetry.value[i] - nominal_interp(telemetry.time[i])
MSE      = mean(error^2)
RMSE     = sqrt(MSE)
MAE      = mean(|error|)
MaxAbsErr = max(|error|)
Euclidean = ||error||_2
```

If the nominal series cannot be interpolated (fewer than 2 points), the
single available nominal value is used as a constant offset; if no nominal
value exists at all, error falls back to the raw telemetry values themselves
so the panel still renders rather than failing outright.

### 6.3 Z-Score Detection

```
z[i] = |value[i] - mean(value)| / std(value)
anomaly[i] = z[i] > threshold        (default threshold = 3.0)
```

Simple, fast, assumes roughly normally-distributed telemetry; this is the
default algorithm in the UI.

### 6.4 Isolation Forest

`sklearn.ensemble.IsolationForest(contamination, n_estimators=100,
random_state=42)` fit on `StandardScaler`-normalized values. Anomalies are
points the ensemble can isolate with few splits. `contamination` (default
0.05) sets the expected anomaly fraction. `random_state=42` is fixed for
reproducible runs.

### 6.5 One-Class SVM

`sklearn.svm.OneClassSVM(nu, gamma='scale', kernel='rbf')` fit on the same
scaled values. `nu` (default 0.05) upper-bounds the fraction of training
points allowed outside the learned boundary.

### 6.6 Severity Classification

Applied only to points already flagged anomalous by whichever algorithm ran:

```
deviation = |value[i] - mean(all values)|
Critical : deviation > 3 * std(all values)
High     : deviation > 2 * std(all values)
Warning  : otherwise (still flagged anomalous, but within 2σ)
```

Note this uses the **raw** values' mean/std (not the scaled values used for
detection), so severity bands are independent of which detection algorithm
produced the flag.

---

## 7. Error Handling & Logging — Current State

- User-facing errors surface through `tkinter.messagebox` (error/warning/info
  dialogs) — this is consistent across both GUI tools.
- Diagnostic detail is written with bare `print()` calls (prefixed `DEBUG:` in
  `curve_analysis.py`), which is acceptable for an interactively-launched
  desktop tool but is not captured anywhere once the terminal/console is
  closed.
- `anomaly_detection.py`'s data-access functions (`get_vehicles`,
  `get_missions`, `get_parameters`, `fetch_data`) each swallow all exceptions
  with a bare `except:` and return an empty result, which keeps the UI from
  crashing but also means a real database error (e.g. a locked file) looks
  identical to "no data" from the user's point of view.
- `insert_bounds_from_files()` is the one place with an explicit transaction
  (`commit`/`rollback`) — appropriate, since it is the only function that
  performs a multi-row delete-then-insert that must succeed or fail as a
  unit.

These are documented here as the as-built behavior rather than prescribed
changes, since altering error-handling behavior is a functional change
outside the scope of this documentation pass.

---

## 8. Deployment Design

### 8.1 Native (no container)

```
pip install -r requirements.txt
python database_creation.py      # once, against a fresh database.db
python database_insertion.py     # whenever new .dat data needs loading
python curve_analysis.py         # or "anomaly_detection.py"
```

### 8.2 Containerized

The application is a Tkinter desktop GUI, not a network service, so the
`Dockerfile` packages the Python runtime and dependencies but does **not**
make the app reachable over a port. Instead, the container's display output
must be forwarded to an X server on the host:

```
FROM python:3.11-slim
   └─ apt: python3-tk, libx11-6, libxext6, libxrender1   (Tk + Matplotlib TkAgg runtime deps)
   └─ pip install -r requirements.txt
   └─ COPY . .
   └─ CMD ["python", "curve_analysis.py"]
```

`docker-compose.yml` defines two services (`curve-analysis`,
`anomaly-detection`) built from the same image, both forwarding `DISPLAY`
and bind-mounting `/tmp/.X11-unix` so GUI windows render on the host's X
server, and both bind-mounting `./database.db` so data persists across
container runs instead of living only inside the container's writable layer.
`network_mode: host` is used so the container can reach the host's X11
socket without per-platform port mapping.

This setup targets Linux hosts with a native X server (the common case for
the SDSC engineering workstations this tool targets). Running the GUI from
Docker Desktop on Windows/macOS needs an additional local X server (e.g.
VcXsrv, XQuartz) and is not covered here, since the project's primary
deployment target is native execution per the README's "Getting Started"
section — the container path is provided as an optional, reproducible
alternative, not a replacement for it.

### 8.3 Image Layer Rationale

| Layer | Reason |
|---|---|
| `python3-tk` | Tkinter is part of CPython's stdlib API but its actual Tcl/Tk binding is an OS package on Debian-based images, not a pip package |
| `libx11-6`, `libxext6`, `libxrender1` | Minimum runtime X11 client libraries Tk and Matplotlib's `TkAgg` backend link against |
| `requirements.txt` copied/installed before `COPY . .` | Lets Docker cache the (slow) dependency install layer across rebuilds that only change application code |

---

## 9. Design Constraints & Technical Debt

1. **Duplicated data-access code** between `curve_analysis.py` and
   `anomaly_detection.py` (`get_vehicles`/`get_missions`/`get_parameters`/
   `fetch_data` each implemented twice, slightly differently — see Section
   4.4's note on silent exception handling in the `anomaly_detection.py`
   copies). A shared `db.py` module would remove this duplication; not done
   here since it would touch both tools' behavior and is outside a
   documentation-only change.
2. **No automated tests.** Both GUI tools are validated manually today.
3. **Hardcoded `DB_FILE = "database.db"`** relative path in every script —
   the working directory at launch time must be the project root.
4. **FR-12/FR-13 gap** — multi-parameter/vehicle overlay and heatmap
   visualization are described in `README.md` but not implemented (tracked
   in `docs/SRS.md` Appendix A).

## 10. Future Architecture Direction

Carried forward from `README.md`'s "Future Enhancements": real-time
telemetry ingestion, LSTM autoencoder / Transformer-based detection,
multivariate (cross-parameter) anomaly detection, adaptive thresholding, and
migration from SQLite to PostgreSQL/Firebase for multi-user access. Any of
these would justify extracting the duplicated data-access layer (Section 9,
item 1) into a shared module first, since both new detection algorithms and
a new database backend would otherwise need to be wired into two independent
codepaths instead of one.
