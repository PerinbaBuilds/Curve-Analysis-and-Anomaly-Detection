import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import pandas as pd
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
import os

# ========= Database File =========
DB_FILE = "database.db"

# ========= DB Connection =========
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# ========= Functions =========
def get_vehicles():
    cursor.execute("SELECT veh_name FROM vehicle")
    return [row[0] for row in cursor.fetchall()]

def get_missions(vehicle):
    cursor.execute("SELECT mission_name FROM mission WHERE veh_id = (SELECT veh_id FROM vehicle WHERE veh_name = ?)", (vehicle,))
    return [row[0] for row in cursor.fetchall()]

def get_parameters(mission):
    cursor.execute("""
        SELECT DISTINCT p.parameter_name FROM parameter p
        JOIN telemetry_data t ON p.parameter_id = t.parameter_id
        WHERE t.mission_id = (SELECT mission_id FROM mission WHERE mission_name = ?)
    """, (mission,))
    return [row[0] for row in cursor.fetchall()]

def fetch_data(mission, parameter):
    cursor.execute("""
        SELECT idx, time, value, validity 
        FROM telemetry_data 
        WHERE mission_id = (SELECT mission_id FROM mission WHERE mission_name = ?)
          AND parameter_id = (SELECT parameter_id FROM parameter WHERE parameter_name = ?)
        ORDER BY time
    """, (mission, parameter))
    rows = cursor.fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["Index", "Time", "Value", "Validity"])
    return df

def check_bounds_existence(mission_id, parameter_id):
    """Check which bounds exist for a given mission and parameter"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT bound_type FROM parameter_bounds 
            WHERE mission_id = ? AND parameter_id = ?
        """, (mission_id, parameter_id))
        
        existing_bounds = [row[0] for row in cursor.fetchall()]
        print(f"DEBUG: Found bounds for mission_id={mission_id}, parameter_id={parameter_id}: {existing_bounds}")
        return existing_bounds
    except Exception as e:
        print(f"DEBUG: Error checking bounds: {e}")
        return []
    finally:
        conn.close()

def read_dat_file(file_path):
    """Read a .dat file and return a DataFrame"""
    try:
        # Read the .dat file - assuming space or tab separated
        df = pd.read_csv(file_path, sep=r'\s+', names=['index', 'time', 'value', 'validity'])
        print(f"DEBUG: Read {len(df)} rows from {file_path}")
        print(f"DEBUG: First few rows:")
        print(df.head())
        print(f"DEBUG: Data types: {df.dtypes}")
        print(f"DEBUG: Null values: {df.isnull().sum()}")
        return df
    except Exception as e:
        messagebox.showerror("File Error", f"Error reading file {file_path}: {str(e)}")
        return None

def debug_table_structure():
    """Debug function to check the parameter_bounds table structure"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(parameter_bounds)")
        columns = cursor.fetchall()
        print("DEBUG: parameter_bounds table structure:")
        for col in columns:
            print(f"  {col}")
        
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='parameter_bounds'")
        table_sql = cursor.fetchone()
        if table_sql:
            print(f"DEBUG: Table creation SQL: {table_sql[0]}")
        
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='parameter_bounds'")
        indexes = cursor.fetchall()
        print("DEBUG: Indexes on parameter_bounds:")
        for idx in indexes:
            print(f"  {idx}")
            
    except Exception as e:
        print(f"DEBUG: Error checking table structure: {e}")
    finally:
        conn.close()

def get_bounds_files_dialog():
    """Create a dialog to select .dat files for bounds"""
    dialog = tk.Toplevel(root)
    dialog.title("Select Bounds Data Files")
    dialog.geometry("500x400")
    dialog.transient(root)
    dialog.grab_set()
    
    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")
    
    tk.Label(dialog, text="Select .dat files for bounds data:", 
             font=("Arial", 12, "bold")).pack(pady=10)
    
    tk.Label(dialog, text="Each file should contain: index  time  value  validity", 
             font=("Arial", 10), fg="gray").pack(pady=5)
    
    # File selection variables
    file_vars = {}
    file_labels = {}
    
    bounds_types = ['upper', 'lower', 'nominal']
    
    for bound_type in bounds_types:
        frame = tk.Frame(dialog)
        frame.pack(pady=10, padx=20, fill='x')
        
        tk.Label(frame, text=f"{bound_type.capitalize()} Bound:", 
                width=15, anchor='w', font=("Arial", 10, "bold")).pack(side='left')
        
        file_var = tk.StringVar()
        file_label = tk.Label(frame, text="No file selected", 
                             width=30, anchor='w', bg="white", relief="sunken")
        file_label.pack(side='left', padx=5)
        
        def make_browse_command(bt, fv, fl):
            def browse_file():
                file_path = filedialog.askopenfilename(
                    title=f"Select {bt} bounds .dat file",
                    filetypes=[("DAT files", "*.dat"), ("All files", "*.*")]
                )
                if file_path:
                    fv.set(file_path)
                    fl.config(text=os.path.basename(file_path))
            return browse_file
        
        browse_btn = tk.Button(frame, text="Browse", 
                              command=make_browse_command(bound_type, file_var, file_label))
        browse_btn.pack(side='left', padx=5)
        
        file_vars[bound_type] = file_var
        file_labels[bound_type] = file_label
    
    result = {'confirmed': False, 'files': {}}
    
    def on_confirm():
        for bound_type in bounds_types:
            if not file_vars[bound_type].get():
                messagebox.showerror("Error", f"Please select a file for {bound_type} bounds.")
                return
        
        for bound_type in bounds_types:
            file_path = file_vars[bound_type].get()
            if not os.path.exists(file_path):
                messagebox.showerror("Error", f"File not found: {file_path}")
                return
            
            test_df = read_dat_file(file_path)
            if test_df is None:
                return
            
            if len(test_df.columns) != 4:
                messagebox.showerror("Error", f"Invalid file format in {os.path.basename(file_path)}. Expected 4 columns: index, time, value, validity")
                return
        
        for bound_type in bounds_types:
            result['files'][bound_type] = file_vars[bound_type].get()
        
        result['confirmed'] = True
        dialog.destroy()
    
    def on_cancel():
        result['confirmed'] = False
        dialog.destroy()
    
    # Buttons
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=20)
    
    tk.Button(button_frame, text="Confirm", command=on_confirm, 
              bg="lightgreen", width=15, height=2).pack(side='left', padx=10)
    tk.Button(button_frame, text="Cancel", command=on_cancel, 
              bg="lightcoral", width=15, height=2).pack(side='left', padx=10)
    
    dialog.wait_window()
    return result

def insert_bounds_from_files(mission_id, parameter_id, bounds_files):
    """Insert bounds data from .dat files into the database using INSERT OR IGNORE"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM parameter_bounds 
            WHERE mission_id = ? AND parameter_id = ?
        """, (mission_id, parameter_id))
        before_count = cursor.fetchone()[0]
        print(f"DEBUG: Records before deletion: {before_count}")
        
        # Delete existing bounds for this mission/parameter combination
        cursor.execute("""
            DELETE FROM parameter_bounds 
            WHERE mission_id = ? AND parameter_id = ?
        """, (mission_id, parameter_id))
        
        cursor.execute("""
            SELECT COUNT(*) FROM parameter_bounds 
            WHERE mission_id = ? AND parameter_id = ?
        """, (mission_id, parameter_id))
        after_count = cursor.fetchone()[0]
        print(f"DEBUG: Records after deletion: {after_count}")
        
        # Insert new data
        total_inserted = 0
        for bound_type, file_path in bounds_files.items():
            print(f"DEBUG: Processing {bound_type} bound from {file_path}")
            
            df = read_dat_file(file_path)
            if df is None:
                print(f"DEBUG: Failed to read file {file_path}")
                conn.rollback()
                return False
            
            print(f"DEBUG: Read {len(df)} rows from {file_path}")
            
            for _, row in df.iterrows():
    # Debug the row data
                print(f"DEBUG: Processing row - index: {row['index']}, time: {row['time']}, value: {row['value']}, validity: {row['validity']}")
    
    # Check if value is None or NaN
                value = row['value']
                if pd.isna(value) or value is None:
                    print(f"WARNING: Skipping row with None/NaN value: {row}")
                    continue
    
                cursor.execute("""
                INSERT OR IGNORE INTO parameter_bounds (mission_id, parameter_id, bound_type, idx, time, value, validity) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (mission_id, parameter_id, bound_type, int(row['index']), 
                float(row['time']), float(value), str(row['validity'])))
                total_inserted += 1
        
        print(f"DEBUG: Total records processed: {total_inserted}")
        
        conn.commit()
        print("DEBUG: Transaction committed successfully")
        
        cursor.execute("""
            SELECT COUNT(*) FROM parameter_bounds 
            WHERE mission_id = ? AND parameter_id = ?
        """, (mission_id, parameter_id))
        final_count = cursor.fetchone()[0]
        print(f"DEBUG: Final record count: {final_count}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"DEBUG: Error occurred: {e}")
        messagebox.showerror("Database Error", f"Failed to insert bounds data: {str(e)}")
        return False
    finally:
        conn.close()

def update_violation_table(filtered):
    for row in violation_table.get_children():
        violation_table.delete(row)
    if not filtered.empty:
        for index, row in filtered.iterrows():
            violation_table.insert("", "end", values=(int(row['Index']), float(row['Time']), float(row['Value']), row['Violation']))

def filter_violations():
    choice = filter_var.get()
    if 'bound_violations' in globals() and not bound_violations.empty:
        if choice == "All":
            update_violation_table(bound_violations)
        else:
            filtered = bound_violations[bound_violations["Violation"] == choice]
            update_violation_table(filtered)

def plot_curve():
    global ax, canvas, metrics_text, summary_text, bound_violations
    global above_count, below_count

    vehicle = vehicle_var.get()
    mission = mission_var.get()
    parameter = parameter_var.get()

    if not vehicle or not mission or not parameter:
        messagebox.showerror("Error", "Please select vehicle, mission, and parameter.")
        return

    df = fetch_data(mission, parameter)
    if df is None or df.empty:
        messagebox.showerror("Error", "No data found for this selection.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Get IDs
    cursor.execute("SELECT mission_id FROM mission WHERE mission_name = ?", (mission,))
    mission_result = cursor.fetchone()
    cursor.execute("SELECT parameter_id FROM parameter WHERE parameter_name = ?", (parameter,))
    parameter_result = cursor.fetchone()

    if not mission_result or not parameter_result:
        messagebox.showerror("Error", "Mission or Parameter not found in DB.")
        conn.close()
        return

    mission_id = mission_result[0]
    parameter_id = parameter_result[0]
    
    print(f"DEBUG: Mission ID: {mission_id}, Parameter ID: {parameter_id}")
    
    conn.close()

    # Check existing bounds
    existing_bounds = check_bounds_existence(mission_id, parameter_id)
    print("============== BOUNDS DEBUG START ==============")
    print(f"Mission: {mission}, Parameter: {parameter}")
    print(f"Mission ID: {mission_id}, Parameter ID: {parameter_id}")
    print("Existing Bounds:", existing_bounds)
    print("============== BOUNDS DEBUG END ================")

    required_bounds = {'upper', 'lower', 'nominal'}
    
    print(f"DEBUG: Existing bounds: {existing_bounds}")
    print(f"DEBUG: Required bounds: {required_bounds}")

    if required_bounds.issubset(set(existing_bounds)):
        print("DEBUG: All bounds exist, proceeding with plotting")
        messagebox.showinfo("Bounds Found", 
                          "All bounds (upper, lower, nominal) already exist for this parameter. Using existing data for plotting.")
    else:
        missing_bounds = required_bounds - set(existing_bounds)
        print(f"DEBUG: Missing bounds: {missing_bounds}")
        
        response = messagebox.askyesno("No Bounds Found", 
                                     f"Bounds data missing for this parameter.\nMissing: {', '.join(missing_bounds)}\n\nWould you like to upload bounds data files (.dat)?")
        if response:
            bounds_input = get_bounds_files_dialog()
            if bounds_input['confirmed']:
                print(f"DEBUG: User selected files: {bounds_input['files']}")
                success = insert_bounds_from_files(mission_id, parameter_id, bounds_input['files'])
                if success:
                    messagebox.showinfo("Success", "Bounds data inserted successfully!")
                    print("DEBUG: Bounds insertion reported success")
                else:
                    print("DEBUG: Bounds insertion failed")
                    return
            else:
                print("DEBUG: User cancelled bounds file selection")
                messagebox.showinfo("Cancelled", "Bounds insertion cancelled. Cannot proceed with plotting.")
                return
        else:
            print("DEBUG: User chose not to upload bounds data")
            messagebox.showinfo("Cancelled", "Cannot plot without bounds data.")
            return

    # Now proceed with plotting using existing/inserted bounds
    conn = sqlite3.connect(DB_FILE)
    df_valid = df[df["Validity"] == 1].copy()

    # Fetch bounds from DB
    # Fetch bounds from DB
    bounds_df = {}
    for b_type in ['nominal', 'upper', 'lower']:
        query = """
        SELECT time, value FROM parameter_bounds 
        WHERE mission_id = ? AND parameter_id = ? AND bound_type = ?
        ORDER BY time
    """
        bounds_df[b_type] = pd.read_sql_query(query, conn, params=(mission_id, parameter_id, b_type))
        print(f"DEBUG: Loaded {len(bounds_df[b_type])} {b_type} bound points")
        print(f"DEBUG: {b_type} bounds data:")
        print(bounds_df[b_type].head())
        if bounds_df[b_type].empty:
            print(f"WARNING: No {b_type} bounds data found!")

    conn.close()

    # Check if bounds data was loaded properly
    if any(bounds_df[b_type].empty for b_type in ['nominal', 'upper', 'lower']):
        messagebox.showerror("Error", "Failed to retrieve bounds data from database.")
        return

    # Clear previous plot
    ax.clear()
    
    # Plot telemetry data first
    ax.plot(df_valid["Time"], df_valid["Value"], label="Actual", color="blue", linewidth=2, zorder=3)
    
    # Plot bounds data with proper colors and styles
    # Plot bounds data with proper colors and styles
    for b_type, color, label in [('nominal', 'orange', 'Nominal'), 
                            ('upper', 'red', 'Upper Bound'), 
                            ('lower', 'green', 'Lower Bound')]:
        if not bounds_df[b_type].empty:
            ax.plot(bounds_df[b_type]['time'], bounds_df[b_type]['value'], 
                label=label, linestyle="--", color=color, linewidth=2, zorder=2)
            print(f"DEBUG: Successfully plotted {b_type} bounds with {len(bounds_df[b_type])} points")
        else:
            print(f"DEBUG: Skipping {b_type} bounds - no data available")

    print(f"DEBUG: Plotted bounds - Upper: {len(bounds_df['upper'])}, Lower: {len(bounds_df['lower'])}, Nominal: {len(bounds_df['nominal'])}")

    # Calculate violations using interpolation
    exceed = pd.Series([False] * len(df_valid))
    below = pd.Series([False] * len(df_valid))
    
    try:
        # Only interpolate if we have sufficient data points
        if len(bounds_df['upper']) > 1 and len(bounds_df['lower']) > 1:
            # Create interpolation functions
            upper_interp = interp1d(bounds_df['upper']['time'], bounds_df['upper']['value'], 
                                  kind='linear', bounds_error=False, fill_value='extrapolate')
            lower_interp = interp1d(bounds_df['lower']['time'], bounds_df['lower']['value'], 
                                  kind='linear', bounds_error=False, fill_value='extrapolate')
            
            # Get interpolated bounds at telemetry time points
            upper_bound_interp = upper_interp(df_valid["Time"])
            lower_bound_interp = lower_interp(df_valid["Time"])
            
            # Find violations
            exceed = df_valid["Value"] > upper_bound_interp
            below = df_valid["Value"] < lower_bound_interp
            
            print(f"DEBUG: Found {exceed.sum()} upper violations and {below.sum()} lower violations")
        else:
            print("DEBUG: Not enough bound data points for interpolation")
            
    except Exception as e:
        print(f"DEBUG: Error in interpolation: {e}")
        # Fallback: no violations detected
        exceed = pd.Series([False] * len(df_valid))
        below = pd.Series([False] * len(df_valid))
    
    # Plot violation points
    if exceed.any():
        ax.scatter(df_valid["Time"][exceed], df_valid["Value"][exceed], 
                  color="red", marker='x', s=100, label="Above Upper", zorder=5)
        print(f"DEBUG: Plotted {exceed.sum()} upper violation points")
    
    if below.any():
        ax.scatter(df_valid["Time"][below], df_valid["Value"][below], 
                  color="green", marker='x', s=100, label="Below Lower", zorder=5)
        print(f"DEBUG: Plotted {below.sum()} lower violation points")

    # Calculate axis limits with proper scaling
    try:
        # Collect all data for proper scaling
        all_times = list(df["Time"])
        all_values = list(df["Value"])
        
        # Add bounds data
        for b_type in ['nominal', 'upper', 'lower']:
            if not bounds_df[b_type].empty:
                all_times.extend(bounds_df[b_type]['time'].tolist())
                all_values.extend(bounds_df[b_type]['value'].tolist())
        
        # Calculate ranges
        time_min, time_max = min(all_times), max(all_times)
        # Filter out None values before calculating min/max
        cleaned_values = [v for v in all_values if v is not None]
        if not cleaned_values:
            messagebox.showerror("Error", "No valid values found for axis scaling.")
            return

        value_min, value_max = min(cleaned_values), max(cleaned_values)

        
        # Add meaningful padding
        time_range = time_max - time_min
        value_range = value_max - value_min
        
        # Use 10% padding or minimum values
        time_padding = max(time_range * 0.1, 50)
        value_padding = max(value_range * 0.1, abs(value_range) * 0.05 if value_range != 0 else 10)
        
        # Use user inputs if provided, otherwise use calculated values
        if xmin_entry.get().strip():
            xmin = float(xmin_entry.get())
        else:
            xmin = time_min - time_padding
            
        if xmax_entry.get().strip():
            xmax = float(xmax_entry.get())
        else:
            xmax = time_max + time_padding
            
        if ymin_entry.get().strip():
            ymin = float(ymin_entry.get())
        else:
            ymin = value_min - value_padding
            
        if ymax_entry.get().strip():
            ymax = float(ymax_entry.get())
        else:
            ymax = value_max + value_padding
        
        print(f"DEBUG: Axis limits - X: [{xmin:.2f}, {xmax:.2f}], Y: [{ymin:.2f}, {ymax:.2f}]")
        
        if xmin >= xmax or ymin >= ymax:
            raise ValueError("Invalid axis limits")
            
    except ValueError as e:
        print(f"DEBUG: Error calculating axis limits: {e}")
        messagebox.showerror("Error", f"Invalid axis limits: {e}")
        return

    # Set axis limits
    ax.set_xlim([xmin, xmax])
    ax.set_ylim([ymin, ymax])
    
    # Format the plot
    ax.set_title(f"{vehicle} → {mission} → {parameter}", fontsize=14, fontweight='bold')
    ax.set_xlabel("Time (sec)", fontsize=12)
    ax.set_ylabel("Value", fontsize=12)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    # Refresh the canvas
    canvas.draw()

    # Calculate metrics using interpolated nominal values
    try:
        if len(bounds_df['nominal']) > 1:
            nominal_interp = interp1d(bounds_df['nominal']['time'], bounds_df['nominal']['value'], 
                                    kind='linear', bounds_error=False, fill_value='extrapolate')
            nominal_values = nominal_interp(df_valid["Time"])
            error = df_valid["Value"].values - nominal_values
        else:
            # Fallback: use constant nominal value if only one point
            nominal_value = bounds_df['nominal']['value'].iloc[0] if not bounds_df['nominal'].empty else 0
            error = df_valid["Value"].values - nominal_value
    except:
        # Last resort: compare against zero
        error = df_valid["Value"].values
    
    # Calculate metrics
    mse = np.mean(error**2)
    mae = np.mean(np.abs(error))
    rmse = np.sqrt(mse)
    max_err = np.max(np.abs(error))
    euclidean = np.linalg.norm(error)

    metrics_text.set(f"""
Mean Squared Error (MSE): {mse:.3f}
Mean Absolute Error (MAE): {mae:.3f}
Root Mean Squared Error (RMSE): {rmse:.3f}
Max Absolute Error: {max_err:.3f}
Euclidean Distance: {euclidean:.3f}
""")
    
    summary_text.set("✔️ Actual values are well within the bounds." if max_err < 5 else "⚠️ Significant deviation detected in actual values.")

    # Update violations table
    violations_list = []
    if exceed.any():
        exceed_data = df_valid[exceed]
        for _, row in exceed_data.iterrows():
            violations_list.append({
                'Index': int(row['Index']),
                'Time': float(row['Time']),
                'Value': float(row['Value']),
                'Violation': 'Above Upper'
            })
    
    if below.any():
        below_data = df_valid[below]
        for _, row in below_data.iterrows():
            violations_list.append({
                'Index': int(row['Index']),
                'Time': float(row['Time']),
                'Value': float(row['Value']),
                'Violation': 'Below Lower'
            })

    bound_violations = pd.DataFrame(violations_list)
    update_violation_table(bound_violations)

    above_count.set(f"Above Upper: {exceed.sum()}")
    below_count.set(f"Below Lower: {below.sum()}")

def update_missions(*args):
    mission_combo['values'] = get_missions(vehicle_var.get())
    mission_var.set('')

def update_parameters(*args):
    parameter_combo['values'] = get_parameters(mission_var.get())
    parameter_var.set('')

# Initialize global variables
bound_violations = pd.DataFrame()

# Debug table structure when the script starts
print("=== DEBUGGING TABLE STRUCTURE ===")
debug_table_structure()
print("=== END DEBUG ===")

root = tk.Tk()
root.title("🚀 Rocket Telemetry Curve Analysis")
root.state('zoomed')

control_frame = tk.Frame(root)
control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

vehicle_var = tk.StringVar()
mission_var = tk.StringVar()
parameter_var = tk.StringVar()
filter_var = tk.StringVar(value="All")
above_count = tk.StringVar()
below_count = tk.StringVar()

entries = [tk.StringVar() for _ in range(4)]
xmin_entry, xmax_entry, ymin_entry, ymax_entry = [tk.Entry(control_frame, textvariable=entries[i], width=10) for i in range(4)]

vehicle_combo = ttk.Combobox(control_frame, textvariable=vehicle_var, values=get_vehicles(), width=15)
mission_combo = ttk.Combobox(control_frame, textvariable=mission_var, width=15)
parameter_combo = ttk.Combobox(control_frame, textvariable=parameter_var, width=15)

labels = ["Vehicle:", "Mission:", "Parameter:", "Xmin:", "Xmax:", "Ymin:", "Ymax:"]
widgets = [vehicle_combo, mission_combo, parameter_combo, xmin_entry, xmax_entry, ymin_entry, ymax_entry]
for i, (lbl, wid) in enumerate(zip(labels, widgets)):
    tk.Label(control_frame, text=lbl).grid(row=0, column=2*i, padx=5)
    wid.grid(row=0, column=2*i+1, padx=5)

plot_button = tk.Button(control_frame, text="Plot Curve", command=plot_curve, bg="lightgreen", font=("Arial", 10, "bold"), width=15, height=2)
plot_button.grid(row=0, column=99, padx=10, sticky="e")

vehicle_combo.bind("<<ComboboxSelected>>", update_missions)
mission_combo.bind("<<ComboboxSelected>>", update_parameters)

main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

plot_frame = tk.Frame(main_frame)
plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

fig, ax = plt.subplots(figsize=(10, 6))
canvas = FigureCanvasTkAgg(fig, master=plot_frame)
canvas.draw()
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
NavigationToolbar2Tk(canvas, plot_frame)

right_frame = tk.Frame(main_frame, bd=2, relief=tk.RIDGE, padx=10, pady=10, width=360)
right_frame.pack(side=tk.RIGHT, fill=tk.Y)
right_frame.pack_propagate(False)

metrics_text = tk.StringVar()
summary_text = tk.StringVar()

metrics_label = tk.Label(right_frame, text="📊 Curve Analysis Metrics", font=("Arial", 12, "bold"))
metrics_label.pack(anchor="center")
metrics_value = tk.Label(right_frame, textvariable=metrics_text, justify="center", anchor="center")
metrics_value.pack(fill="x", pady=5)

summary_label = tk.Label(right_frame, text="📝 Summary", font=("Arial", 12, "bold"))
summary_label.pack(anchor="center", pady=(10, 0))
summary_value = tk.Label(right_frame, textvariable=summary_text, justify="center", anchor="center", wraplength=330)
summary_value.pack(fill="x", pady=5)

violation_label = tk.Label(right_frame, text="⚠️ Bound Violations", font=("Arial", 12, "bold"))
violation_label.pack(anchor="center", pady=(10, 0))

filter_frame = tk.Frame(right_frame)
filter_frame.pack(pady=5)
filter_inner = tk.Frame(filter_frame)
filter_inner.pack(anchor="center")

filter_label = tk.Label(filter_inner, text="Filter:")
filter_label.pack(side=tk.LEFT, padx=5)
tt_filter = ttk.Combobox(filter_inner, textvariable=filter_var, values=["All", "Above Upper", "Below Lower"], width=17, state="readonly")
tt_filter.pack(side=tk.LEFT, padx=5)
filter_button = tk.Button(filter_inner, text="Apply", command=filter_violations)
filter_button.pack(side=tk.LEFT, padx=5)

violation_table_frame = tk.Frame(right_frame)
violation_table_frame.pack(fill="x")

violation_table = ttk.Treeview(violation_table_frame, columns=("Index", "Time", "Value", "Violation"), show="headings", height=8)
column_widths = {"Index": 60, "Time": 80, "Value": 80, "Violation": 130}
for col, width in column_widths.items():
    violation_table.heading(col, text=col)
    violation_table.column(col, anchor="center", stretch=False, width=width)
violation_table.pack(fill=tk.X)

count_frame = tk.Frame(right_frame)
count_frame.pack(fill="x", pady=5)
tk.Label(count_frame, textvariable=above_count, anchor="center").pack(anchor="center")
tk.Label(count_frame, textvariable=below_count, anchor="center").pack(anchor="center")

root.mainloop()
conn.close()

