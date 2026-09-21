import os
import sys

ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "script.module.ambientwled", "lib")
)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
