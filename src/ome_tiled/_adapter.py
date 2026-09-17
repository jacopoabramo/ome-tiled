from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import zarr
from tiled.adapters.zarr import ZarrArrayAdapter, ZarrGroupAdapter
from tiled.structures.array import ArrayStructure
from tiled.utils import path_from_uri
from zarr.errors import GroupNotFoundError

from ome_tiled._ngff import NgffImage, NgffSkipped, classify

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


# tiled ships no type information, so its classes are Any to mypy
class OmeZarrAdapter(ZarrGroupAdapter):  # type: ignore[misc]
    """Serve OME-Zarr images as arrays with their axis names.

    Register it under ``OME_ZARR_MIMETYPE``. An image registered by its group
    or by its full-resolution array reads as one array whose ``dims`` are the
    axes' names, with the axes in the metadata under ``axes``. A group holding
    images presents each as such an array. Any other group, including NGFF
    layouts this package does not read and metadata that fails validation, is
    served as ``tiled``'s Zarr adapter serves it.
    """

    def __getitem__(self, key: str) -> Any:
        value = self._zarr_group[key]
        if isinstance(value, zarr.Group):
            return open_group(value)
        return super().__getitem__(key)

    @classmethod
    def from_uris(cls, data_uri: str, **kwargs: Any) -> Any:
        """Open the group or array at *data_uri*."""
        return open_path(path_from_uri(data_uri), **kwargs)

    @classmethod
    def from_catalog(cls, data_source: Any, node: Any, /, **kwargs: Any) -> Any:
        """Open a registered asset, keeping the structure stored with it."""
        return open_path(
            path_from_uri(data_source.assets[0].data_uri),
            structure=data_source.structure,
            metadata=node.metadata_,
            specs=node.specs,
            **kwargs,
        )


def open_path(
    path: Path, *, structure: ArrayStructure | None = None, **kwargs: Any
) -> Any:
    """Return the adapter for the group or array at *path*."""
    node = zarr.open(path, mode="r")
    if isinstance(node, zarr.Group):
        return open_group(node, structure=structure, **kwargs)
    try:
        parent = zarr.open_group(path.parent, mode="r")
    except GroupNotFoundError:
        image = None
    else:
        image = classify(parent.attrs.asdict())
    if isinstance(image, NgffImage):
        return open_image(node, image, structure=structure, **kwargs)
    return ZarrArrayAdapter(
        node, structure or ArrayStructure.from_array(node), **kwargs
    )


def open_group(
    group: zarr.Group, *, structure: ArrayStructure | None = None, **kwargs: Any
) -> Any:
    """Return an image's array adapter for an image group, a group adapter otherwise."""
    image = classify(group.attrs.asdict())
    if isinstance(image, NgffImage):
        array = group.get(image.path)
        if isinstance(array, zarr.Array):
            return open_image(array, image, structure=structure, **kwargs)
        image = NgffSkipped(f"dataset {image.path!r} is not an array")
    if isinstance(image, NgffSkipped):
        logger.info("Serving %s as plain Zarr: %s", group.store_path, image.reason)
    return OmeZarrAdapter(group, **kwargs)


def open_image(
    array: zarr.Array[Any],
    image: NgffImage,
    *,
    structure: ArrayStructure | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Return an array adapter carrying the image's axis names and axes."""
    return ZarrArrayAdapter(
        array,
        structure or ArrayStructure.from_array(array, dims=image.dims),
        metadata={**(metadata or {}), "axes": [dict(axis) for axis in image.axes]},
        **kwargs,
    )
