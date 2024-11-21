""" Adapters to present various Mantid interfaces as Python Mapping
"""

from typing import Any

from collections.abc import Mapping

from mantid.api import Run

def mappingFromRun(run: Run) -> Mapping:
    # Normalize `mantid.api.run` to a standard Python Mapping.
    
    class _Mapping(Mapping):
        
        def __init__(self, run: Run):
            self._run = run
            
        def __getitem__(self, key: str) -> Any:
            try:
                value = self._run.getProperty(key).value
            except RuntimeError as e:
                if "Unknown property search object" in str(e):
                    raise KeyError(key) from e
                raise
            return value
        
        def __iter__(self):
            return self._run.keys().__iter__()
            
        def __len__(self,):
            return len(self._run.keys())
            
        def __contains__(self, key: str):
            return self._run.hasProperty(key)
            
        def keys(self):
            return self._run.keys()

    return _Mapping(run)
