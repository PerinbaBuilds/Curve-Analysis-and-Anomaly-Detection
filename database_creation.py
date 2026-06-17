import sqlite3

# Connect to SQLite DB
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# VEHICLE TABLE
cursor.execute("""
CREATE TABLE vehicle (
    veh_id INTEGER PRIMARY KEY AUTOINCREMENT,
    veh_name VARCHAR UNIQUE NOT NULL,
    height REAL,
    weight REAL,
    payload_type VARCHAR
);
""")

# MISSION TABLE
cursor.execute("""
CREATE TABLE mission (
    mission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    veh_id INTEGER NOT NULL,
    mission_name VARCHAR UNIQUE NOT NULL,
    launch_date DATE,
    status VARCHAR,
    launch_pad VARCHAR,
    FOREIGN KEY (veh_id) REFERENCES vehicle(veh_id)
);
""")

# PARAMETER TABLE
cursor.execute("""
CREATE TABLE parameter (
    parameter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parameter_name VARCHAR UNIQUE NOT NULL
);
""")

# TELEMETRY DATA TABLE
cursor.execute("""
CREATE TABLE telemetry_data (
    mission_id INTEGER NOT NULL,
    parameter_id INTEGER NOT NULL,
    idx INTEGER  NOT NULL,
    time REAL NOT NULL,
    value REAL,
    validity BOOLEAN,
    PRIMARY KEY (mission_id, parameter_id, time),
    FOREIGN KEY (mission_id) REFERENCES mission(mission_id),
    FOREIGN KEY (parameter_id) REFERENCES parameter(parameter_id)
);
""")

# SIMULATED PARTITIONING: Composite index for fast access
cursor.execute("""
CREATE INDEX idx_mission_param_time ON telemetry_data (mission_id, parameter_id, time);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS parameter_bounds (
    mission_id INTEGER NOT NULL,
    parameter_id INTEGER NOT NULL,
    bound_type TEXT CHECK(bound_type IN ('upper', 'lower', 'nominal')) NOT NULL,
    idx INTEGER NOT NULL,
    time DATETIME NOT NULL,
    value REAL,
    validity TEXT,
    PRIMARY KEY (mission_id, parameter_id, bound_type, idx),
    FOREIGN KEY (mission_id) REFERENCES mission(mission_id),
    FOREIGN KEY (parameter_id) REFERENCES parameter(parameter_id)
);
""")

# Commit and close
conn.commit()
conn.close()

print("🚀 Optimized schema created successfully.")
