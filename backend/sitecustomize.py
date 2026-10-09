import sys
from importlib.abc import MetaPathFinder
from importlib.util import spec_from_file_location
import os

class PurePythonFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if "sqlalchemy" in fullname and fullname.endswith("_cy"):
            if path:
                for p in path:
                    mod_name = fullname.split(".")[-1]
                    py_file = os.path.join(p, f"{mod_name}.py")
                    if os.path.isfile(py_file):
                        return spec_from_file_location(fullname, py_file)
        return None

sys.meta_path.insert(0, PurePythonFinder())
