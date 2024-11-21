from mantid.simpleapi import (
    CreateSampleWorkspace,
    DeleteWorkspace,
    LoadInstrument,
    mtd,
)

from snapred.backend.data.util.mapping_util import *
from snapred.meta.Config import Resource

import unittest
from unittest import mock
import pytest

class TestMapping(unittest.TestCase):

    def setUp(self):
        self.wsName = mtd.unique_hidden_name()
        CreateSampleWorkspace(
            OutputWorkspace=self.wsName,
            # WorkspaceType="Histogram",
            Function="User Defined",
            UserDefinedFunction="name=Gaussian,Height=10,PeakCentre=1.2,Sigma=0.2",
            Xmin=0,
            Xmax=5,
            BinWidth=0.001,
            XUnit="dSpacing",
            NumBanks=4,  # must produce same number of pixels as fake instrument
            BankPixelWidth=2,  # each bank has 4 pixels, 4 banks, 16 total
        )
        LoadInstrument(
            Workspace=self.wsName,
            Filename=Resource.getPath("inputs/testInstrument/fakeSNAP_Definition.xml"),
            RewriteSpectraMap=True,
        )
        self.ws = mtd[self.wsName]

    def tearDown(self):
        DeleteWorkspace(self.wsName)
        
    def test_mappingFromRun_init(self):
        runMapping = mappingFromRun(self.ws.getRun())

    def test_mappingFromRun_get_item(self):
        map = mappingFromRun(self.ws.getRun())
        assert map["run_title"] == "Test Workspace"
        assert map["start_time"] == "2010-01-01T00:00:00"
        assert map["end_time"] == "2010-01-01T01:00:00"
        
    def test_mappingFromRun_iter(self):
        map = mappingFromRun(self.ws.getRun())
        assert [k for k in map] == ['run_title', 'start_time', 'end_time', 'run_start', 'run_end']
    
    def test_mappingFromRun_len(self):
        map = mappingFromRun(self.ws.getRun())
        assert len(map) == 5
        
    @mock.patch("mantid.api.Run.hasProperty")
    def test_mappingFromRun_contains(self, mockHasProperty):
        mockHasProperty.return_value = True
        map = mappingFromRun(self.ws.getRun())
        assert "anything" in map
        mockHasProperty.assert_called_once_with("anything")
        
    @mock.patch("mantid.api.Run.keys")
    def test_mappingFromRun_keys(self, mockKeys):
        mockKeys.return_value = ["we", "are", "the", "keys"]
        map = mappingFromRun(self.ws.getRun())
        assert map.keys() == mockKeys.return_value
        mockKeys.assert_called_once()
        
