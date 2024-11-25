from enum import Flag, auto
from typing import Any, Optional

from pydantic import BaseModel, model_validator

from snapred.backend.log.logger import snapredLogger

logger = snapredLogger.getLogger(__name__)


class LiveStateChange(Exception):
    """
    Raised when a live-data run changes state.
    """

    class Type(Flag):
        UNSET = 0
        
        # <run number> > 0 <- <run number> == 0
        RUN_START = auto()
        
        # <run number> == 0 <- <run number> > 0
        RUN_END = auto()
        
        # <run number>` != <run number>  <- <run number> > 0
        RUN_GAP = auto()

    class Model(BaseModel):
        message: str
        flags: "LiveStateChange.Type"
        
        endRunNumber: str
        startRunNumber: str
 
    def __init__(self, message: str, flags: "Type" = 0, endRunNumber: str, startRunNumber: str):
        LiveStateChange.Model.model_rebuild(force=True)
        self.model = LiveStateChange.Model(message=message, flags=flags, endRunNumber=endRunNumber, startRunNumber=startRunNumber)
        super().__init__(message)

    @property
    def message(self):
        return self.model.message

    @property
    def flags(self):
        return self.model.flags

    @property
    def endRunNumber(self):
        return self.model.endRunNumber

    @property
    def startRunNumber(self):
        return self.model.startRunNumber

    @staticmethod    
    def parse_raw(raw) -> "LiveStateChange":
        raw = LiveStateChange.Model.model_validate_json(raw)
        return LiveStateChange(**raw.dict())

    @staticmethod    
    def runStateTransition(endRunNumber: str, startRunNumber: str) -> "LiveStateChange":
        transition = LiveStateChange.Type.UNSET
        if int(endRunNumber) > 0 and int(startRunNumber) == 0:
            transition = LiveStateChange.Type.RUN_START
        elif int(endRunNumber) == 0 and int(startRunNumber) > 0:
            transition = LiveStateChange.Type.RUN_END
        elif int(endRunNumber) > 0 and int(startRunNumber) > 0:
            transition = LiveStateChange.Type.RUN_GAP
        else:
            raise ValidationError(f"Not a possible run-state transition: {endRunNumber} <- {startRunNumber}")
            
        return LiveStateChange(
            "Run number change",
            flags=LiveStateChange.Type.RUN_STATE,
            endRunNumber=endRunNumber,
            startRunNumber=startRunNumber
        )

    @model_validator(mode="after")
    def _validate_LiveStateChange(self):
        if self.endRunNumber == self.startRunNumber:
            raise ValidationError(f"Not a run-state transition: {self.endRunNumber} <- {self.startRunNumber}")
        return self
