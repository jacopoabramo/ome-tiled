from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import yaozarrs
from pydantic import ValidationError
from yaozarrs import v04, v05

if TYPE_CHECKING:
    from collections.abc import Mapping

OME_ZARR_MIMETYPE: Final = "application/x-ome-zarr"
"""Mimetype under which a catalog routes OME-Zarr data to ``OmeZarrAdapter``."""

IMAGES: Final = (v04.Image, v04.LabelImage, v05.Image, v05.LabelImage)


@dataclass(frozen=True)
class NgffImage:
    """An OME-Zarr image, reduced to what serving it as one array needs.

    Attributes
    ----------
    dims : tuple[str, ...]
        Axis names, in array order.
    axes : tuple[Mapping[str, Any], ...]
        Each axis as the metadata writes it: ``name``, ``type`` and ``unit``
        when present.
    path : str
        Path of the full-resolution array, relative to the image group.
    """

    dims: tuple[str, ...]
    axes: tuple[Mapping[str, Any], ...]
    path: str


@dataclass(frozen=True)
class NgffSkipped:
    """An OME-Zarr group this package does not serve, and why."""

    reason: str


def classify(attributes: Mapping[str, Any]) -> NgffImage | NgffSkipped | None:
    """Classify a Zarr group by its attributes.

    Returns
    -------
    NgffImage | NgffSkipped | None
        ``NgffImage`` for an NGFF 0.4 or 0.5 image or label image,
        ``NgffSkipped`` for any other NGFF layout and for NGFF metadata that
        fails validation, and ``None`` for a group that is not NGFF.
    """
    try:
        node = yaozarrs.validate_ome_object(dict(attributes))
    except ValidationError as error:
        # the errors do not tell a plain group from a broken image, so the keys
        # decide whether the group claimed to be NGFF at all
        if "ome" in attributes or "multiscales" in attributes:
            return NgffSkipped(f"NGFF metadata failed validation: {error}")
        return None
    if isinstance(node, v05.OMEAttributes):
        node = node.ome
    if not isinstance(node, IMAGES):
        return NgffSkipped(type(node).__name__)
    multiscale = node.multiscales[0]
    axes = tuple(axis.model_dump(exclude_none=True) for axis in multiscale.axes)
    return NgffImage(
        dims=tuple(axis["name"] for axis in axes),
        axes=axes,
        path=multiscale.datasets[0].path,
    )
