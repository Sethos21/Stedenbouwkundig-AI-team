from typing import Protocol
from copy import deepcopy
from bvc_ai.domain.policies import K00Policy

class DocumentRepository(Protocol):
    def read(self, reference: str) -> dict: ...
    def write(self, reference: str, document: dict) -> None: ...

DriveRepository = DocumentRepository

class GISAdapter(Protocol):
    def read(self, asset_id: str) -> dict: ...
    def register_layer(self, asset_id: str, data: dict, *, origin: str, classification: str) -> None: ...

GISRepository = GISAdapter

class MockDocumentRepository:
    def __init__(self):
        self._documents = {}
    def read(self, reference):
        return deepcopy(self._documents[reference])
    def write(self, reference, document):
        self._documents[reference] = deepcopy(document)

class MockGISAdapter:
    def __init__(self):
        self._layers = {"K00": {"source_status": "TESTDATA", "geometry": None, "immutable": True}}
    def read(self, asset_id):
        return deepcopy(self._layers[asset_id.strip().upper()])
    def register_layer(self, asset_id, data, *, origin="derived", classification="derived"):
        K00Policy.authorize(asset_id, "write", origin=origin, classification=classification)
        self._layers[asset_id.strip().upper()] = deepcopy(data)
