Curve Analysis and Anomaly Detection Tool


Overview
This project is a Python-based desktop tool for analyzing rocket telemetry data and detecting anomalies in mission parameters.
It enables engineers and analysts to visualize parameter curves, detect anomalies using machine learning algorithms, and export results for further study.

Key Features
Curve Analysis

Fetches mission telemetry data from an SQLite database.

Plots parameter curves against nominal upper and lower bounds.

Highlights bound violations on the curve.

Anomaly Detection

Supports Z-Score, Isolation Forest, and One-Class SVM algorithms.

Detects deviations and highlights anomalous data points.

Displays detected anomalies in an interactive table with severity levels.

Visualization

Interactive matplotlib-based plots embedded in a Tkinter GUI.

Right-side panel for algorithm summaries and anomalies table.

Data Handling

Fetches data dynamically from the database.

Option to export anomaly results as CSV.

Anomalies are not stored in the database (CSV-only export).

Tech Stack
Programming Language: Python 3.8+

GUI: Tkinter

Data Handling: Pandas, SQLite3

Machine Learning: Scikit-learn

Visualization: Matplotlib

How It Works
Select Mission and Parameter

Dropdown menus fetch missions, vehicles, and telemetry parameters from the database.

Curve Plotting

Plots parameter curves with upper/lower bounds.

Anomaly Detection

Choose an algorithm and detect anomalies.

View & Export Results

Anomalies displayed in a table.

Export results as a CSV file.

Screenshots
(Insert screenshots of the GUI here – curve analysis panel and anomaly detection panel)

Future Enhancements
Enhanced right-side summary and severity visualization.

Additional anomaly detection algorithms.

Improved curve visualization with multi-parameter overlay.
