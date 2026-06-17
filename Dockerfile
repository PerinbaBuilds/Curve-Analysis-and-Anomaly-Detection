# Telemetry Curve Analysis & Anomaly Detection
#
# This is a Tkinter desktop GUI application, not a web service. The
# container does not run a display server itself - it must be given
# access to a host X11 display to show any window. See README.md /
# docker-compose.yml for the host-side flags required to do that.
FROM python:3.11-slim

# python3-tk          - Tkinter bindings (not installable via pip)
# libx11-6/libxext6/libxrender1 - runtime X11 client libraries used by
#                         Tk and Matplotlib's TkAgg backend
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-tk \
        libx11-6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Forwarded from the host so GUI windows render on the host's X server.
ENV DISPLAY=:0

# database.db is expected in the working directory at runtime (mount it
# as a volume - see docker-compose.yml - so data persists between runs).
CMD ["python", "curve_analysis.py"]
