""" Adapters to present various Mantid interfaces as Python Mapping
"""
from collections.abc import Mapping
import h5py
from typing import Any

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

def mappingFromNeXusLogs(h5: h5py.File) -> Mapping:
    # Normalize NeXus hdf5 logs to a standard Python Mapping.
    
    class _Mapping(Mapping):
        
        def __init__(self, h5: h5py.File):
            self._logs = h5.open_group("entry/DASlogs")
            
        def __getitem__(self, key: str) -> Any:
            return self._logs[key + "/value"]
        
        def __iter__(self):
            return self.keys().__iter__()
            
        def __len__(self,):
            return len(self._logs.keys())
            
        def __contains__(self, key: str):
            return self._logs.__contains__(key + "/value")
            
        def keys(self):
            return [k[0: k.rfind("/value")] for k in self._logs.keys()]

    return _Mapping(h5)
