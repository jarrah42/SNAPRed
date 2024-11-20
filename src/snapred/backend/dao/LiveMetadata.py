from typing import ClassVar
from datetime import datetime
from pydantic import BaseModel

from mantid.api import Run

from snapred.backend.dao.state import DetectorState


class LiveMetadata:
    """Metadata about any in-progress data acquisition."""
    
    # Implementation notes:
    #
    #   * If there's no run currently active, the `runNumber` will be `INACTIVE_RUN`.
    #
    #   * Metadata may change at any time.  For example, the run may terminate and become inactive.
    #     For this reason, in most cases this DAO should never be cached.
    #
    
    INACTIVE_RUN: ClassVar[int] = 0
    
    runNumber: str
    startTime: datetime
    endTime: datetime
    
    detectorState: DetectorState
 
    def hasActiveRun(self):
        return int(runNumber) != INACTIVE_RUN

    @staticmethod
    def _datetimeFromTimeStr(time: str) -> datetime:
        # Convert from near ISO to ISO: strip three digits from the tail
        return datetime.fromisoformat(time[0:-3])
        
    @classmethod
    def fromRun(cls, run: Run) -> "LiveMetaData":        
        return LiveMetaData(
            runNumber=run.getProperty('run_number').value,
            startTime=cls._datetimeFromTimeStr(run.getProperty('start_time').value),
            endTime=cls._datetimeFromTimeStr(run.getProperty('end_time').value),
            detectorState=DetectorState.fromRun(run)
        )
