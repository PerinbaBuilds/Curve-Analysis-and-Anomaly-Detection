import os
import sqlite3
import pandas as pd

# 🔥 Database file (make sure this matches yours)
DB_FILE = "database.db"

# 📂 Main data folder path (update if needed)
data_folder = os.path.join(os.path.expanduser("~"), "Desktop", "rocket_data")


# 🚀 Connect to database
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()


# ==============================================
# 🔥 Helper Functions to Manage ID Mappings
# ==============================================
def get_or_create_vehicle(vehicle_name):
    cursor.execute("SELECT veh_id FROM vehicle WHERE veh_name = ?", (vehicle_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        cursor.execute(
            "INSERT INTO vehicle (veh_name, height, weight, payload_type) VALUES (?, ?, ?, ?)",
            (vehicle_name, 50.0, 500.0, 'Satellite')
        )
        conn.commit()
        return cursor.lastrowid


def get_or_create_mission(mission_name, veh_id):
    cursor.execute("SELECT mission_id FROM mission WHERE mission_name = ?", (mission_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        cursor.execute(
            "INSERT INTO mission (veh_id, mission_name, launch_date, status, launch_pad) VALUES (?, ?, ?, ?, ?)",
            (veh_id, mission_name, '2023-01-01', 'Completed', 'SHAR')
        )
        conn.commit()
        return cursor.lastrowid


def get_or_create_parameter(parameter_name):
    cursor.execute("SELECT parameter_id FROM parameter WHERE parameter_name = ?", (parameter_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        cursor.execute(
            "INSERT INTO parameter (parameter_name) VALUES (?)",
            (parameter_name,)
        )
        conn.commit()
        return cursor.lastrowid


# ==============================================
# 🚀 Main Data Ingestion Logic
# ==============================================
for folder_name in os.listdir(data_folder):
    folder_path = os.path.join(data_folder, folder_name)
    if not os.path.isdir(folder_path):
        continue

    print(f"\n📂 Processing folder: {folder_name}")

    # Split folder name like 'pslv_c59' → vehicle='pslv', mission='c59'
    try:
        vehicle_part, mission_part = folder_name.split('_')
        vehicle_name = vehicle_part.upper()  # e.g., PSLV
        mission_name = folder_name.lower()   # e.g., pslv_c59
    except ValueError:
        print(f"⚠️ Skipping invalid folder name: {folder_name}")
        continue

    veh_id = get_or_create_vehicle(vehicle_name)
    mission_id = get_or_create_mission(mission_name, veh_id)

    for file in os.listdir(folder_path):
        if not file.endswith(".dat"):
            continue

        parameter_name = file.replace('.dat', '')
        parameter_id = get_or_create_parameter(parameter_name)

        file_path = os.path.join(folder_path, file)
        print(f"➡️ Inserting {file}...")

        try:
            df = pd.read_csv(file_path, sep=r'\s+', header=None, names=['Index', 'Time', 'Value', 'Validity'])
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            continue

        records = [
            (mission_id, parameter_id, int(row['Index']), float(row['Time']),
             float(row['Value']), int(row['Validity']))
            for _, row in df.iterrows()
        ]

        cursor.executemany(
            "INSERT OR IGNORE INTO telemetry_data (mission_id, parameter_id, idx, time, value, validity) VALUES (?, ?, ?, ?, ?, ?)",
            records
        )
        conn.commit()
        print(f"✅ Inserted {len(records)} rows for {parameter_name}.")

print("\n🎉 Data insertion completed successfully!")

# ✅ Close connection
conn.close()
