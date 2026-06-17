# Exploratory Data Analysis on Launch Vehicle Telemetry Data

An interactive desktop application for analysing launch vehicle telemetry data through curve deviation analysis and machine learning-based anomaly detection. Developed at Satish Dhawan Space Centre (SDSC-SHAR), ISRO, as part of an academic internship.

> **Note:** This public repository is a replicated, sample version of the original work for portfolio and demonstration purposes. The primary implementation was carried out at SDSC-SHAR, ISRO, using real mission telemetry data; that original codebase and data are confidential and cannot be published. This repository reproduces the same system design and functionality on sample data.

## Objective

To develop a compact, interactive desktop tool that enables engineers to perform curve deviation analysis and anomaly detection on launch vehicle telemetry data. The system reduces manual effort by combining machine learning algorithms with real-time visualisations, allowing analysts to identify abnormal patterns across mission datasets with configurable thresholds and severity classification.

## Key Features

**Curve Analysis**
- Loads telemetry time-series data from a structured SQLite database
- Supports upload of `.dat` reference bound files (nominal, upper, lower) when pre-existing bounds are absent
- Interpolates bounds across telemetry timestamps using `scipy.interpolate.interp1d`
- Detects and highlights bound violations (above upper, below lower) directly on the plot
- Computes five deviation metrics: MSE, RMSE, MAE, Maximum Absolute Error, Euclidean Distance

**Multi-Parameter and Multi-Vehicle Comparison**
- Overlay multiple parameters from the same vehicle on a single plot for side-by-side analysis
- Compare parameters across different vehicles and missions simultaneously
- Supports cross-mission analysis to identify recurring anomaly patterns

**Anomaly Detection**
- Three selectable algorithms: Z-Score, Isolation Forest, One-Class SVM
- Pre-processes data with Z-score normalisation before detection
- Classifies each anomaly by severity based on standard deviation from mean:
  - Critical: deviation greater than 3 standard deviations
  - High: deviation greater than 2 standard deviations
  - Warning: deviation within 2 standard deviations
- Results displayed in a filterable, scrollable table within the GUI
- Export anomalies as CSV

**Heatmap Visualisation**
- Generates a heatmap of anomaly distribution across time and severity levels
- Provides a high-level overview of anomaly concentration across the dataset

**Visualisation**
- Interactive Matplotlib plot embedded in the Tkinter GUI via `FigureCanvasTkAgg`
- Full navigation toolbar (zoom, pan, save) integrated into the interface
- Telemetry plotted in blue; nominal bound in orange dashed; upper bound in red dashed; lower bound in green dashed; violations marked with distinct point markers

## System Architecture

The application follows a layered, modular design with four independent components that integrate into a single workflow:

    User Input (GUI)
         |
         v
    Database Handler  -->  Telemetry Data (telemetry_data table)
         |                 Bounds Data    (parameter_bounds table)
         v
    Preprocessing Engine  -->  Z-score normalisation, outlier trimming
         |
         v
    Anomaly / Curve Engine  -->  Z-Score / Isolation Forest / One-Class SVM
         |                       Bound interpolation, violation detection
         v
    Visualisation & Export  -->  Matplotlib plot, heatmap, anomaly table, CSV export

**GUI Layout**
- Top Control Panel: dropdowns for vehicle, mission, telemetry parameter, and algorithm selection
- Left Panel: interactive time-series plot and heatmap view
- Right Panel: deviation metrics, summary verdict, severity table with filter controls

## Database Schema

The application connects to a local SQLite database (`database.db`) with the following structure:

| Table | Description |
|---|---|
| `vehicle` | Launch vehicle records |
| `mission` | Missions linked to each vehicle |
| `parameter` | Telemetry parameter definitions |
| `telemetry_data` | Time-series readings (time, value, validity flag) |
| `parameter_bounds` | Nominal, upper, and lower bound values per mission and parameter |
| `anomaly_results` | Detected anomaly records (optional storage) |

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.8.5 |
| GUI | Tkinter |
| Data Handling | Pandas, NumPy, SQLite3 |
| Visualisation | Matplotlib |
| Machine Learning | Scikit-learn |
| Interpolation | SciPy |
| Development Environment | PyCharm 2021.1, Windows 10 |

## Documentation

| Document | Description |
|---|---|
| [docs/SRS.md](docs/SRS.md) | Software Requirements Specification — functional & non-functional requirements |
| [docs/SDD.md](docs/SDD.md) | Software Design Document — architecture, data design, algorithms, deployment |

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Required packages: `pandas`, `numpy`, `matplotlib`, `scikit-learn`, `scipy`

Install all dependencies:

    pip install -r requirements.txt

A `Dockerfile` and `docker-compose.yml` are also provided for a containerized, reproducible environment — see [Running with Docker](#running-with-docker) below.

### Database Setup

The application reads/writes a local SQLite database named `database.db` in the project root. To build it from scratch:

    python database_creation.py      # creates the schema (run once per new database.db)
    python database_insertion.py     # bulk-loads .dat telemetry files into it

`database_insertion.py` expects telemetry `.dat` files under `~/Desktop/rocket_data/<vehicle>_<mission>/<parameter>.dat` — see `docs/SRS.md` (Section 2.6) for the exact folder/file convention. Reference bounds (nominal/upper/lower) can instead be supplied later, on demand, through the Curve Analysis GUI itself (see Usage Workflow step 2 below).

### Running the Application

Curve Analysis module:

    python curve_analysis.py

Anomaly Detection module:

    python anomaly_detection.py

### Running with Docker

This is a Tkinter desktop GUI, not a web service, so the container forwards its display to the host's X server rather than exposing a port. On Linux:

    xhost +local:docker
    docker compose run --rm curve-analysis
    docker compose run --rm anomaly-detection
    xhost -local:docker

`database.db` is bind-mounted into the container so data persists between runs. See `docs/SDD.md` (Section 8) for the full deployment design and rationale.

## Usage Workflow

1. **Select parameters** — Use the dropdown menus to choose a vehicle, mission, and telemetry parameter. Dropdowns populate dynamically from the database.
2. **Load bounds** — If reference bounds are not already in the database, the application will prompt for `.dat` files (one each for nominal, upper, and lower bounds). Each file must contain columns: `index`, `time`, `value`, `validity`.
3. **Plot the curve** — Click "Plot Curve" to render the telemetry data with overlaid bounds. Violations are highlighted automatically and deviation metrics are computed.
4. **Multi-parameter or multi-vehicle comparison** — Select additional parameters or a different vehicle to overlay curves for comparative analysis.
5. **Run anomaly detection** — Select a detection algorithm and click the detect button. Anomalies are marked on the plot and listed in the table with severity labels.
6. **View heatmap** — Switch to the heatmap view to see the distribution and concentration of anomalies across time and severity.
7. **Filter and export** — Filter the anomaly table by severity or violation type. Export results as a `.csv` file for external review.

## Anomaly Detection Algorithms

**Z-Score**
Statistical method. Computes the number of standard deviations each data point lies from the mean. Points exceeding the configured threshold are flagged as anomalies. Best suited for normally distributed telemetry.

**Isolation Forest**
Unsupervised ensemble method. Builds random isolation trees and identifies anomalies as points that require fewer splits to isolate. Effective on high-dimensional data without assumptions about distribution.

**One-Class SVM**
Supervised boundary learning method. Trains on normal telemetry to define a decision boundary. Points falling outside the boundary are classified as outliers. Well-suited to scenarios where labelled anomaly data is unavailable.

## Deviation Metrics

| Metric | Description |
|---|---|
| MSE | Mean Squared Error — average of squared differences from nominal |
| RMSE | Root Mean Squared Error — square root of MSE, in original units |
| MAE | Mean Absolute Error — average of absolute differences |
| Max Absolute Error | Largest single deviation observed |
| Euclidean Distance | L2 norm of the error vector across the full time series |

## Future Enhancements

- Real-time telemetry stream integration for live mission monitoring
- LSTM autoencoder and Transformer-based anomaly detection for complex temporal patterns
- Multivariate anomaly detection based on inter-parameter relationships
- Adaptive thresholding driven by historical trends and data variability
- Migration to PostgreSQL or Firebase for multi-user and large-scale dataset support
- Role-based access control for collaborative environments

## Acknowledgements

This project was developed during an internship at Satish Dhawan Space Centre (SDSC-SHAR), ISRO, under the supervision of Smt. Ramaneeswari.T, Deputy Manager, Specialists' Display Systems (SDS), Range Operations (RO). 
