"""Write OME-Zarr acquisitions into a catalog through ``TiledWriter``.

Needs the ``bluesky`` extra, which installs ``bluesky-tiled-plugins``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from bluesky_tiled_plugins.writing.consolidators import (
    CONSOLIDATOR_REGISTRY,
    ConsolidatorBase,
)

from ome_tiled._adapter import OmeZarrAdapter
from ome_tiled._ngff import OME_ZARR_MIMETYPE

if TYPE_CHECKING:
    from tiled.structures.array import ArrayStructure

__all__ = ["OmeZarrConsolidator", "register_consolidator"]


# bluesky-tiled-plugins ships no type information, so its classes are Any to mypy
class OmeZarrConsolidator(ConsolidatorBase):  # type: ignore[misc]
    """Consolidate a ``StreamResource`` naming an OME-Zarr image.

    The structure registered is the image's own, read from the store: its shape,
    chunks and axis names. ``ConsolidatorBase`` computes one from the documents
    instead, as the number of rows times the shape of each, which does not match
    a store holding more dimensions than a row has.
    """

    supported_mimetypes: ClassVar[set[str]] = {OME_ZARR_MIMETYPE}

    def structure(self) -> ArrayStructure:
        """Return the structure of the image at the resource's URI."""
        structure: ArrayStructure = OmeZarrAdapter.from_uris(self.uri).structure()
        return structure


def register_consolidator() -> None:
    """Have ``TiledWriter`` consolidate ``OME_ZARR_MIMETYPE`` resources here."""
    CONSOLIDATOR_REGISTRY[OME_ZARR_MIMETYPE] = OmeZarrConsolidator
