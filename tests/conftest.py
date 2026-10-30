import os
import sys

# the tests import uds_builder (this folder) and the package (one level up)
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
