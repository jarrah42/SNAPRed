from typing import Any

from pydantic import BaseModel, field_validator

from snapred.backend.dao.GSASParameters import GSASParameters
from snapred.backend.dao.InstrumentConfig import InstrumentConfig
from snapred.backend.dao.Limit import Pair
from snapred.backend.dao.ObjectSHA import ObjectSHA
from snapred.backend.dao.ParticleBounds import ParticleBounds
from snapred.backend.dao.state.DetectorState import DetectorState, GuideState


class InstrumentState(BaseModel):
    # Use the StateId hash to enforce filesystem-as-database integrity requirements:
    # * verify that this InstrumentState's file is at its expected location (e.g. it hasn't been moved);
    # * verify that any nested JSON components that are in separate files are at their expected locations.
    id: ObjectSHA

    instrumentConfig: InstrumentConfig
    detectorState: DetectorState
    gsasParameters: GSASParameters
    particleBounds: ParticleBounds
    defaultGroupingSliceValue: float
    fwhmMultipliers: Pair[float]
    peakTailCoefficient: float

    @property
    def delTh(self) -> float:
        return (
            self.instrumentConfig.delThWithGuide
            if self.detectorState.guideStat == GuideState.IN
            else self.instrumentConfig.delThNoGuide
        )

    @field_validator("fwhmMultipliers", mode="before")
    @classmethod
    def validate_fwhmMultipliers(cls, v: Any) -> Pair[float]:
        if isinstance(v, dict):
            v = Pair[float](**v)
        if not isinstance(v, Pair[float]):
            # Coerce Generic[T]-derived type
            v = Pair[float](**v.dict())
        return v

    @field_validator("id", mode="before")
    @classmethod
    def str_to_ObjectSHA(cls, v: Any) -> Any:
        # ObjectSHA to be stored in JSON as _only_ a single hex string, for the hex digest itself
        if isinstance(v, str):
            return ObjectSHA(hex=v, decodedKey=None)
        return v
