""" Adapters to present various Mantid interfaces as Python Mapping
"""
from collections.abc import Mapping
import datetime
import h5py
import numpy as np
from typing import Any

from mantid.api import Run

def mappingFromRun(run: Run) -> Mapping:
    # Normalize `mantid.api.run` to a standard Python Mapping.
    
    class _Mapping(Mapping):
        
        def __init__(self, run: Run):
            self._run = run
            
        def __getitem__(self, key: str) -> Any:
            # Too many special cases in the logs!
            value = None
            match key:
                case 'start_time':
                    # Convert from nanosecond to microsecond time resolution:
                    #   whether this is acceptable or not depends on the intended use case.
                    # For end users selecting live-data duration based on the run start time, this works fine.
                    value = np.datetime64(self._run.startTime().to_datetime64(), "us").astype(datetime.datetime)
                case 'end_time':
                    value = np.datetime64(self._run.endTime().to_datetime64(), "us").astype(datetime.datetime)
                case 'run_number':
                    value = self._run.getProperty('run_number') if self._run.hasProperty('run_number') else 0
                case _:
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
            self._logs = h5["entry/DASlogs"]
            
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
