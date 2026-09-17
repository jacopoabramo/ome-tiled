from __future__ import annotations

import pytest
from tiled.utils import import_object

import ome_tiled

# written out rather than read from __all__, so a name dropped from the package
# fails here instead of leaving nothing to parametrize
CONFIGURATION_STRINGS = ["ome_tiled:APPLICATION_OME_ZARR"]


@pytest.mark.parametrize("path", CONFIGURATION_STRINGS)
def test_configuration_strings_resolve_through_the_package(path: str) -> None:
    name = path.partition(":")[2]
    assert import_object(path) is getattr(ome_tiled, name)
