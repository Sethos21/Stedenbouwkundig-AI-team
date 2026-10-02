"""A06 discovery capability. No interpretation, store writes or agent activation."""
from copy import deepcopy
from datetime import datetime, timezone

from bvc_ai.adapters.dso_contract import digest
from bvc_ai.adapters.dso_discovery import DSODiscoveryAdapter, CRS
from bvc_ai.application.spatial_context import SpatialContextService


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class DSODiscoveryService:
    def __init__(self, transport, *, clock=_utc_now):
        self._adapter = DSODiscoveryAdapter(transport)
        self._clock = clock

    def discover_point(self, point_rd, *, peildatum, beschikbaar_op):
        result = self._adapter.discover(point_rd, peildatum=peildatum,
                                        beschikbaar_op=beschikbaar_op, clock=self._clock)
        result.update(format='BVC_A06_DSO_DISCOVERY_V1',
                      limitations=['DOCUMENT_CANDIDATES_NOT_LEGAL_RULES_OR_CONSTRAINTS',
                                   'POINT_QUERY_NOT_FULL_ANALYSIS_SCOPE',
                                   'ONE_COMPLETE_PAGE_MAXIMUM_200_DOCUMENTS',
                                   'NO_GEOMETRY_DOWNLOAD_OR_A02_REGISTRATION',
                                   'RELATED_VERSIONS_RETAINED_NOT_SELECTED_OR_FETCHED'])
        result['discovery_hash'] = digest(result)
        return result

    def discover_a02_point(self, store, spatial_context, record_ref, *, peildatum, beschikbaar_op):
        """Trusted local entrypoint; downstream runtime receives data, never Store.

        Only an explicit existing point fact may be used. No centroid, bbox-centre
        inference or relabelling of a DSO working area as A02 EXISTING_VALIDATED.
        """
        spatial = deepcopy(spatial_context)
        reader = SpatialContextService(store)
        reader.verify(spatial)
        objects = [o for o in spatial['objects'] if o['record_ref'] == record_ref]
        if len(objects) != 1:
            raise ValueError('Unique A02 point record required')
        positions = [f for f in objects[0]['facts'] if f['name'] == 'position']
        if len(positions) != 1 or positions[0]['method'] != 'SOURCE_COORDINATES':
            raise ValueError('Explicit A02 source point required')
        evidence = spatial['provenance'][positions[0]['provenance_ref']]
        # A02 point facts are already validated RD coordinates.
        result = self.discover_point(positions[0]['value'], peildatum=peildatum,
                                     beschikbaar_op=beschikbaar_op)
        result['a02_binding'] = dict(context_hash=spatial['context_hash'],
                                     revision_id=spatial['revision_id'],
                                     record_ref=deepcopy(record_ref),
                                     geometry_ref=evidence['geometry_ref'],
                                     geometry_structural_hash=evidence['geometry_structural_hash'],
                                     query_crs=CRS)
        reader.verify(spatial)
        del result['discovery_hash']
        result['discovery_hash'] = digest(result)
        return result
