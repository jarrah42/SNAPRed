from enum import IntEnum
import h5py
from numbers import Number
from typing import Literal, Tuple
from pydantic import BaseModel, field_validator, ValidationError

from mantid.api import Run


class GuideState(IntEnum):
    IN = 1
    OUT = 2


class DetectorState(BaseModel):
    arc: Tuple[float, float]
    wav: float
    freq: float
    guideStat: Literal[1, 2]
    # two additional values that don't define state, but are useful
    lin: Tuple[float, float]

    @staticmethod
    def fromRun(run: Run) -> "DetectorState":
        detectorState = None
        wav_key_1 = "BL3:Chop:Gbl:WavelengthReq"
        wav_key_2 = "BL3:Chop:Skf1:WavelengthUserReq"
        try:
            detectorState = DetectorState(
                arc=[run.getProperty("det_arc1").value[0], run.getProperty("det_arc2").value[0]],
                wav=run.getProperty("BL3:Chop:Gbl:WavelengthReq").value[0] if run.hasProperty(wav_key_1)\
                    else run.getProperty(wav_key_2).value[0],
                freq=run.getProperty("BL3:Det:TH:BL:Frequency").value[0],
                guideStat=run.getProperty("BL3:Mot:OpticsPos:Pos").value[0],
                lin=[run.getProperty("det_lin1").value[0], run.getProperty("det_lin2").value[0]]
            )
        except (RuntimeError, TypeError) as e:
            raise RuntimeError("Workspace does not have all required logs to assemble a DetectorState") from e
            
        return detectorState

    @staticmethod
    def fromHDF5(pvFile: h5py.File) -> "DetectorState":
        detectorState = None
        wav_value = None
        wav_key_1 = "entry/DASlogs/BL3:Chop:Gbl:WavelengthReq/value"
        wav_key_2 = "entry/DASlogs/BL3:Chop:Skf1:WavelengthUserReq/value"
        
        try:
            detectorState = DetectorState(
                arc=[pvFile.get("entry/DASlogs/det_arc1/value")[0], pvFile.get("entry/DASlogs/det_arc2/value")[0]],
                wav=pvFile.get(wav_key_1)[0] if wav_key_1 in pvFile else pvFile.get(wav_key_2)[0],
                freq=pvFile.get("entry/DASlogs/BL3:Det:TH:BL:Frequency/value")[0],
                guideStat=pvFile.get("entry/DASlogs/BL3:Mot:OpticsPos:Pos/value")[0],
                lin=[pvFile.get("entry/DASlogs/det_lin1/value")[0], pvFile.get("entry/DASlogs/det_lin2/value")[0]],
            )
        except (KeyError, TypeError, ValidationError) as e:
            raise RuntimeError("Neutron data file does not include all required logs to assemble a DetectorState") from e
            
        return detectorState
            
    @field_validator("guideStat", mode="before")
    @classmethod
    def validate_int(cls, v):
        if isinstance(v, Number) and not isinstance(v, int):
            # accept any Number type: convert to `int`:
            #   e.g. hdf5 returns `int64`
            v = int(v)
        return v
