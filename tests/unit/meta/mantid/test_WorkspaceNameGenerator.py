import pytest
from snapred.meta.mantid.WorkspaceNameGenerator import WorkspaceNameGenerator as wng

runNumber = 123
fRunNumber = str(runNumber).zfill(6)
version = 1
fVersion = "v" + str(version).zfill(4)
stateId = "ab8704b0bc2a2342"
fStateId = "bc2a2342"


def testRunNames():
    assert "tof_all_" + fRunNumber == wng.run().runNumber(runNumber).build()
    assert "dsp_all_" + fRunNumber == wng.run().runNumber(runNumber).unit(wng.Units.DSP).build()
    assert (
        "dsp_column_" + fRunNumber
        == wng.run().runNumber(runNumber).unit(wng.Units.DSP).group(wng.Groups.COLUMN).build()
    )
    assert (
        "dsp_column_test_" + fRunNumber
        == wng.run().runNumber(runNumber).unit(wng.Units.DSP).group(wng.Groups.COLUMN).auxiliary("Test").build()
    )


def testDiffCalInputNames():
    assert "_tof_" + fRunNumber + "_raw" == wng.diffCalInput().runNumber(runNumber).build()
    assert "_dsp_" + fRunNumber + "_raw" == wng.diffCalInput().runNumber(runNumber).unit(wng.Units.DSP).build()


def testDiffCalOutputName():
    assert f"_tof_unfoc_{fRunNumber}" == wng.diffCalOutput().runNumber(runNumber).unit(wng.Units.TOF).build()
    assert (
        f"_tof_unfoc_{fRunNumber}_{fVersion}"
        == wng.diffCalOutput().runNumber(runNumber).unit(wng.Units.TOF).version(version).build()
    )

def testDiffCalDiagnosticName():
    assert f"_diagnostic_unfoc_{fRunNumber}" == wng.diffCalDiagnostic().runNumber(runNumber).build()
    assert (
        f"_diagnostic_unfoc_{fRunNumber}_{fVersion}"
        == wng.diffCalDiagnostic().runNumber(runNumber).version(version).build()
    )


def testDiffCalTableName():
    assert f"_diffract_consts_{fRunNumber}" == wng.diffCalTable().runNumber(runNumber).build()
    assert (
        f"_diffract_consts_{fRunNumber}_{fVersion}" == wng.diffCalTable().runNumber(runNumber).version(version).build()
    )


def testDiffCalMaskName():
    assert f"_diffract_consts_mask_{fRunNumber}" == wng.diffCalMask().runNumber(runNumber).build()
    assert (
        f"_diffract_consts_mask_{fRunNumber}_{fVersion}"
        == wng.diffCalMask().runNumber(runNumber).version(version).build()
    )


def testDiffCalMetricsNames():
    assert (
        f"_calib_metrics_strain_{fRunNumber}" == wng.diffCalMetric().runNumber(runNumber).metricName("strain").build()
    )
    assert (
        f"_calib_metrics_strain_{fRunNumber}_{fVersion}"
        == wng.diffCalMetric().metricName("strain").runNumber(runNumber).version(version).build()
    )


def testReductionOutputName():
    assert (  # "reduced_data,{unit},{group},{runNumber},{version}"
        f"_reduced_dsp_lahdeedah_{fRunNumber}" == wng.reductionOutput().group("lahDeeDah").runNumber(runNumber).build()
    )
    assert (
        f"_reduced_dsp_column_{fRunNumber}_{fVersion}"
        == wng.reductionOutput().group(wng.Groups.COLUMN).runNumber(runNumber).version(version).build()
    )
    assert (
        f"_reduced_tof_column_{fRunNumber}_{fVersion}"
        == wng.reductionOutput()
        .unit(wng.Units.TOF)
        .group(wng.Groups.COLUMN)
        .runNumber(runNumber)
        .version(version)
        .build()
    )


def testReductionOutputGroupName():
    assert (  # "reduced_data,{stateId},{version}"
        f"_reduced_{fStateId}" == wng.reductionOutputGroup().stateId(stateId).build()
    )
    assert f"_reduced_{fStateId}_{fVersion}" == wng.reductionOutputGroup().stateId(stateId).version(version).build()


def testInvalidKey():
    with pytest.raises(RuntimeError, match=r"Key \[unit\] not a valid property"):
        wng.diffCalMask().runNumber(runNumber).unit(wng.Units.TOF).build()
