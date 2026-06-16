import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import time
import os

# ==================== DB CONNECTION ====================
DB_FILE = "database.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# ==================== GLOBAL VARIABLES ====================
anomalies_df = pd.DataFrame()  # Global variable to store anomalies
current_data = pd.DataFrame()  # Store current dataset for accuracy calculation

# ==================== FETCH FUNCTIONS ====================
def get_vehicles():
    try:
        cursor.execute("SELECT veh_name FROM vehicle")
        return [row[0] for row in cursor.fetchall()]
    except:
        return []

def get_missions(vehicle):
    try:
        cursor.execute("SELECT mission_name FROM mission WHERE veh_id = (SELECT veh_id FROM vehicle WHERE veh_name = ?)", (vehicle,))
        return [row[0] for row in cursor.fetchall()]
    except:
        return []

def get_parameters(mission):
    try:
        cursor.execute("""
            SELECT DISTINCT p.parameter_name FROM parameter p
            JOIN telemetry_data t ON p.parameter_id = t.parameter_id
            WHERE t.mission_id = (SELECT mission_id FROM mission WHERE mission_name = ?)
        """, (mission,))
        return [row[0] for row in cursor.fetchall()]
    except:
        return []

def fetch_data(mission, parameter):
    try:
        cursor.execute("""
            SELECT time, value FROM telemetry_data
            WHERE mission_id = (SELECT mission_id FROM mission WHERE mission_name = ?)
              AND parameter_id = (SELECT parameter_id FROM parameter WHERE parameter_name = ?)
            ORDER BY time
        """, (mission, parameter))
        rows = cursor.fetchall()
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=["Time", "Value"])
        return df
    except:
        return None

# ==================== ACCURACY CALCULATION ====================
def calculate_accuracy(y_true, y_pred):
    """Calculate accuracy for anomaly detection"""
    try:
        # For unsupervised learning, we'll use a heuristic approach
        # Assume that points beyond 2 standard deviations are true anomalies
        return len(y_pred[y_pred == -1]) / len(y_pred) if len(y_pred) > 0 else 0
    except:
        return 0

# ==================== SEVERITY CLASSIFICATION ====================
def classify_severity(values, anomaly_indices):
    """Classify anomalies into Critical, High, and Warning based on deviation"""
    if len(values) == 0 or len(anomaly_indices) == 0:
        return []
    
    mean_val = np.mean(values)
    std_val = np.std(values)
    
    severities = []
    for idx in anomaly_indices:
        deviation = abs(values[idx] - mean_val)
        if deviation > 3 * std_val:
            severities.append("Critical")
        elif deviation > 2 * std_val:
            severities.append("High")
        else:
            severities.append("Warning")
    
    return severities

# ==================== DETECT ANOMALIES ====================
def detect_anomalies():
    global anomalies_df, current_data
    
    vehicle = vehicle_var.get()
    mission = mission_var.get()
    parameter = parameter_var.get()
    algo = algo_var.get()

    if not (vehicle and mission and parameter and algo):
        messagebox.showerror("Error", "Please select all options.")
        return

    df = fetch_data(mission, parameter)
    if df is None or df.empty:
        messagebox.showerror("Error", "No data available for selected parameters.")
        return

    current_data = df.copy()
    X = df[["Value"]].values
    
    # Handle potential NaN values
    X = X[~np.isnan(X).any(axis=1)]
    if len(X) == 0:
        messagebox.showerror("Error", "No valid data points found.")
        return
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Initialize variables
    anomaly_score = 0
    preds = None

    if algo == "Z-Score":
        z_scores = np.abs((X.flatten() - np.mean(X)) / np.std(X))
        threshold = float(threshold_var.get()) if threshold_var.get() else 3.0
        anomaly_mask = z_scores > threshold
        preds = np.where(anomaly_mask, -1, 1)
        anomaly_score = np.sum(anomaly_mask) / len(X) * 100
        summary.set(f"Z-Score: Points with |Z| > {threshold} marked as anomalies.")
        
    elif algo == "Isolation Forest":
        contamination = float(contamination_var.get()) if contamination_var.get() else 0.05
        model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        preds = model.fit_predict(X_scaled)
        anomaly_score = np.sum(preds == -1) / len(preds) * 100
        summary.set(f"Isolation Forest: Contamination={contamination:.2f}, isolates anomalies using random forests.")
        
    elif algo == "One-Class SVM":
        nu = float(nu_var.get()) if nu_var.get() else 0.05
        model = OneClassSVM(nu=nu, gamma='scale', kernel='rbf')
        preds = model.fit_predict(X_scaled)
        anomaly_score = np.sum(preds == -1) / len(preds) * 100
        summary.set(f"One-Class SVM: nu={nu:.2f}, finds decision boundary around normal data.")

    # Update dataframe with predictions
    df_subset = df.iloc[:len(preds)].copy()
    df_subset["Anomaly"] = preds == -1
    
    # Get anomaly indices and classify severity
    anomaly_indices = np.where(preds == -1)[0]
    if len(anomaly_indices) > 0:
        severities = classify_severity(X.flatten(), anomaly_indices)
        df_subset["Severity"] = "Normal"
        df_subset.loc[df_subset["Anomaly"], "Severity"] = severities
    else:
        df_subset["Severity"] = "Normal"

    # Store anomalies globally
    anomalies_df = df_subset[df_subset["Anomaly"]].copy()
    
    # Display accuracy/score
    score_display.set(f"Anomaly Rate: {anomaly_score:.2f}%")

    # Plot results
    ax.clear()
    ax.plot(df_subset["Time"], df_subset["Value"], label="Normal Data", color="blue", alpha=0.7)
    
    if len(anomalies_df) > 0:
        # Plot different severity levels with different colors
        critical = anomalies_df[anomalies_df["Severity"] == "Critical"]
        high = anomalies_df[anomalies_df["Severity"] == "High"]
        warning = anomalies_df[anomalies_df["Severity"] == "Warning"]
        
        if len(critical) > 0:
            ax.scatter(critical["Time"], critical["Value"], color="red", label="Critical", marker='X', s=100)
        if len(high) > 0:
            ax.scatter(high["Time"], high["Value"], color="orange", label="High", marker='D', s=80)
        if len(warning) > 0:
            ax.scatter(warning["Time"], warning["Value"], color="yellow", label="Warning", marker='o', s=60)
    
    ax.set_title(f"{vehicle} → {mission} → {parameter} ({algo})")
    ax.set_xlabel("Time")
    ax.set_ylabel("Value")
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Adjust layout
    fig.tight_layout()
    canvas.draw()

    # Update table with all anomalies
    update_anomaly_table()

    # Reset filter to "All"
    filter_type.set("All")

    # Save anomalies with timestamp
    if len(anomalies_df) > 0:
        timestamp = str(int(time.time()))
        filename = f"anomalies_{vehicle}_{mission}_{parameter}_{algo}_{timestamp}.csv"
        try:
            anomalies_df.to_csv(filename, index=False)
            status_var.set(f"Saved: {filename}")
        except Exception as e:
            status_var.set(f"Save failed: {str(e)}")
    else:
        status_var.set("No anomalies detected")

def update_anomaly_table():
    """Update the anomaly table with current data"""
    # Clear existing entries
    for i in anomaly_table.get_children():
        anomaly_table.delete(i)
    
    if anomalies_df.empty:
        return
    
    # Add all anomalies to table
    for _, row in anomalies_df.iterrows():
        anomaly_table.insert("", "end", values=(
            f"{row['Time']:.2f}", 
            f"{row['Value']:.3f}", 
            row["Severity"]
        ))

def filter_table():
    """Filter the anomaly table based on severity selection"""
    global anomalies_df
    
    if anomalies_df.empty:
        messagebox.showwarning("Warning", "No anomalies to filter. Please run detection first.")
        return
    
    selection = filter_type.get()
    
    # Clear existing entries
    for i in anomaly_table.get_children():
        anomaly_table.delete(i)
    
    # Filter data based on selection
    if selection == "All":
        filtered = anomalies_df
    else:
        filtered = anomalies_df[anomalies_df['Severity'] == selection]
    
    # Populate table with filtered data
    for _, row in filtered.iterrows():
        anomaly_table.insert("", "end", values=(
            f"{row['Time']:.2f}", 
            f"{row['Value']:.3f}", 
            row["Severity"]
        ))
    
    # Update status
    status_var.set(f"Filtered: {len(filtered)} {selection.lower()} anomalies")

# ==================== GUI ====================
root = tk.Tk()
root.title("📈 Anomaly Detection System v2.0")
root.geometry("1400x800")
root.configure(bg="#f0f0f0")

# Variables
vehicle_var = tk.StringVar()
mission_var = tk.StringVar()
parameter_var = tk.StringVar()
algo_var = tk.StringVar(value="Z-Score")
summary = tk.StringVar()
score_display = tk.StringVar()
status_var = tk.StringVar(value="Ready")

# Algorithm-specific parameters
threshold_var = tk.StringVar(value="3.0")  # Z-Score threshold
contamination_var = tk.StringVar(value="0.05")  # Isolation Forest contamination
nu_var = tk.StringVar(value="0.05")  # One-Class SVM nu parameter

# ==== Top Controls ====
top_frame = tk.Frame(root, bg="#f0f0f0")
top_frame.pack(fill=tk.X, padx=10, pady=10)

# First row - main controls
control_frame1 = tk.Frame(top_frame, bg="#f0f0f0")
control_frame1.pack(fill=tk.X, pady=(0, 5))

labels = ["Vehicle", "Mission", "Parameter", "Algorithm"]
for i, label in enumerate(labels):
    tk.Label(control_frame1, text=label+":", bg="#f0f0f0").grid(row=0, column=i*2, padx=5, sticky="w")

vehicle_menu = ttk.Combobox(control_frame1, textvariable=vehicle_var, values=get_vehicles(), width=15)
vehicle_menu.grid(row=0, column=1, padx=5)

mission_menu = ttk.Combobox(control_frame1, textvariable=mission_var, width=15)
mission_menu.grid(row=0, column=3, padx=5)

parameter_menu = ttk.Combobox(control_frame1, textvariable=parameter_var, width=15)
parameter_menu.grid(row=0, column=5, padx=5)

algo_menu = ttk.Combobox(control_frame1, textvariable=algo_var, 
                        values=["Z-Score", "Isolation Forest", "One-Class SVM"], width=18)
algo_menu.grid(row=0, column=7, padx=5)

detect_btn = tk.Button(control_frame1, text="🔍 Detect Anomalies", command=detect_anomalies, 
                      bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
detect_btn.grid(row=0, column=8, padx=10)

# Second row - parameter controls
control_frame2 = tk.Frame(top_frame, bg="#f0f0f0")
control_frame2.pack(fill=tk.X)

tk.Label(control_frame2, text="Z-Score Threshold:", bg="#f0f0f0").grid(row=0, column=0, padx=5, sticky="w")
tk.Entry(control_frame2, textvariable=threshold_var, width=8).grid(row=0, column=1, padx=5)

tk.Label(control_frame2, text="IF Contamination:", bg="#f0f0f0").grid(row=0, column=2, padx=5, sticky="w")
tk.Entry(control_frame2, textvariable=contamination_var, width=8).grid(row=0, column=3, padx=5)

tk.Label(control_frame2, text="SVM Nu:", bg="#f0f0f0").grid(row=0, column=4, padx=5, sticky="w")
tk.Entry(control_frame2, textvariable=nu_var, width=8).grid(row=0, column=5, padx=5)

# Status bar
status_label = tk.Label(control_frame2, textvariable=status_var, bg="#f0f0f0", fg="blue")
status_label.grid(row=0, column=6, padx=20, sticky="w")

# Dropdown update functions
def update_missions(*args):
    vehicle = vehicle_var.get()
    if vehicle:
        missions = get_missions(vehicle)
        mission_menu['values'] = missions
        mission_var.set('')
        parameter_menu.set('')
        parameter_menu['values'] = []

def update_parameters(*args):
    mission = mission_var.get()
    if mission:
        parameters = get_parameters(mission)
        parameter_menu['values'] = parameters
        parameter_var.set('')

vehicle_menu.bind("<<ComboboxSelected>>", update_missions)
mission_menu.bind("<<ComboboxSelected>>", update_parameters)

# ==== Main Split Frame ====
main_frame = tk.Frame(root, bg="#f0f0f0")
main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# ==== Left Plot ====
left_frame = tk.Frame(main_frame, bg="white", relief=tk.RAISED, bd=1)
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

fig, ax = plt.subplots(figsize=(10, 6))
fig.patch.set_facecolor('white')
canvas = FigureCanvasTkAgg(fig, master=left_frame)
canvas.draw()
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
toolbar = NavigationToolbar2Tk(canvas, left_frame)
toolbar.update()

# ==== Right Info Panel ====
right_frame = tk.Frame(main_frame, bg="white", relief=tk.RAISED, bd=1)
right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

# Set fixed width for right frame
right_frame.config(width=400)
right_frame.pack_propagate(False)

# Right frame content
info_frame = tk.Frame(right_frame, bg="white")
info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Summary Box
tk.Label(info_frame, text="📋 Algorithm Summary", font=("Arial", 12, "bold"), bg="white").pack(anchor="w")
summary_label = tk.Label(info_frame, textvariable=summary, wraplength=350, justify="left", 
                        fg="gray", bg="white")
summary_label.pack(anchor="w", pady=(0,10))

# Score Box
tk.Label(info_frame, text="📊 Detection Statistics", font=("Arial", 12, "bold"), bg="white").pack(anchor="w")
score_label = tk.Label(info_frame, textvariable=score_display, fg="darkblue", bg="white", 
                      font=("Arial", 10, "bold"))
score_label.pack(anchor="w", pady=(0,15))

# Anomaly Table Title
tk.Label(info_frame, text="🚨 Anomaly Details", font=("Arial", 12, "bold"), bg="white").pack(anchor="w")

# Filter controls
filter_frame = tk.Frame(info_frame, bg="white")
filter_frame.pack(fill=tk.X, pady=(5,10))

tk.Label(filter_frame, text="Filter by Severity:", bg="white").pack(side=tk.LEFT)
filter_type = ttk.Combobox(filter_frame, values=["All", "Critical", "High", "Warning"], 
                          state="readonly", width=12)
filter_type.set("All")
filter_type.pack(side=tk.LEFT, padx=(10,5))

filter_btn = tk.Button(filter_frame, text="Apply Filter", command=filter_table, 
                      bg="#2196F3", fg="white", font=("Arial", 9))
filter_btn.pack(side=tk.LEFT, padx=5)

# Anomaly Table
table_frame = tk.Frame(info_frame, bg="white")
table_frame.pack(fill=tk.BOTH, expand=True)

# Create treeview with scrollbars
anomaly_table = ttk.Treeview(table_frame, columns=("Time", "Value", "Severity"), 
                            show="headings", height=15)

# Configure columns
anomaly_table.heading("Time", text="Time")
anomaly_table.heading("Value", text="Value")
anomaly_table.heading("Severity", text="Severity")

anomaly_table.column("Time", width=90, anchor="center")
anomaly_table.column("Value", width=90, anchor="center")
anomaly_table.column("Severity", width=90, anchor="center")

# Scrollbars
v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=anomaly_table.yview)
h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=anomaly_table.xview)

anomaly_table.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

# Pack table and scrollbars
anomaly_table.grid(row=0, column=0, sticky="nsew")
v_scrollbar.grid(row=0, column=1, sticky="ns")
h_scrollbar.grid(row=1, column=0, sticky="ew")

table_frame.grid_rowconfigure(0, weight=1)
table_frame.grid_columnconfigure(0, weight=1)

# Initialize display
summary.set("Select parameters and click 'Detect Anomalies' to start analysis.")
score_display.set("No analysis performed yet.")

# Run the application
if __name__ == "__main__":
    root.mainloop()
    try:
        conn.close()
    except:
        pass
