import json
import os
import platform
import socket
import sys
import time

name = sys.argv[1] if len(sys.argv) > 1 else ""

result = {
    "greeting": f"Hello from Python, {name}!",
    "runner": {
        "hostname": socket.gethostname(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pythonVersion": platform.python_version(),
        "pythonImplementation": platform.python_implementation(),
        "cpuCount": os.cpu_count(),
        "workingDirectory": os.getcwd(),
        "timezone": time.tzname[0],
    },
}

print(json.dumps(result, indent=2))
