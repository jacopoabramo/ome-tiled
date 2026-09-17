from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from tiled.client import from_uri
from tiled.client.register import register
from tiled.structures.core import StructureFamily
from tiled.structures.data_source import Asset, DataSource, Management

from ome_tiled import OME_ZARR_MIMETYPE, OmeZarrAdapter

if TYPE_CHECKING:
    from pathlib import Path

    from tiled.client.container import Container
    from tiled.server.simple import SimpleTiledServer

FOUR_DIMS = ("t", "z", "y", "x")
THREE_DIMS = ("t", "y", "x")


def register_image(client: Container, key: str, uri: str) -> Any:
    """Register one image as `tiled register` would, from the adapter's view of it."""
    adapter = OmeZarrAdapter.from_uris(uri)
    return client.new(
        key=key,
        structure_family=StructureFamily.array,
        data_sources=[
            DataSource(
                management=Management.external,
                mimetype=OME_ZARR_MIMETYPE,
                structure_family=StructureFamily.array,
                structure=adapter.structure(),
                assets=[Asset(data_uri=uri, is_directory=True, parameter="data_uri")],
            )
        ],
        metadata=dict(adapter.metadata()),
        specs=[],
    )


@pytest.mark.parametrize("suffix", ["", "/0"], ids=["group-path", "array-path"])
@pytest.mark.parametrize(
    ("store", "image", "dims", "shape"),
    [
        ("ome_writers_acquire_zarr_store", "", FOUR_DIMS, (2, 3, 8, 8)),
        ("ome_writers_zarr_python_store", "", FOUR_DIMS, (2, 3, 8, 8)),
        ("acquire_zarr_store", "/det", THREE_DIMS, (2, 16, 16)),
        ("ngff04_store", "", FOUR_DIMS, (2, 3, 8, 8)),
        ("ngff05_store", "", FOUR_DIMS, (2, 3, 8, 8)),
        ("custom_axis_store", "", ("pattern", "z", "y", "x"), (2, 3, 8, 8)),
    ],
)
def test_registered_image_reads_with_axis_names(
    client: Container,
    request: pytest.FixtureRequest,
    store: str,
    image: str,
    dims: tuple[str, ...],
    shape: tuple[int, ...],
    suffix: str,
) -> None:
    path: Path = request.getfixturevalue(store)
    node = register_image(client, "image", path.as_uri() + image + suffix)

    assert node.structure().dims == dims
    assert node.read().shape == shape
    assert node.read().sum() > 0


def test_axis_units_reach_the_node_metadata(
    client: Container, ome_writers_acquire_zarr_store: Path
) -> None:
    node = register_image(client, "image", ome_writers_acquire_zarr_store.as_uri())

    units = {axis["name"]: axis.get("unit") for axis in node.metadata["axes"]}
    assert units == {"t": None, "z": "micrometer", "y": None, "x": None}


@pytest.mark.usefixtures("acquire_zarr_store")
def test_walked_store_presents_each_image_as_a_named_array(
    client: Container, data_dir: Path
) -> None:
    anyio.run(
        lambda: register(
            client,
            data_dir,
            adapters_by_mimetype={OME_ZARR_MIMETYPE: OmeZarrAdapter},
            mimetypes_by_file_ext={".zarr": OME_ZARR_MIMETYPE},
        )
    )
    store = client["run"]

    assert sorted(store) == ["det", "det_median"]
    for key in store:
        assert store[key].structure().dims == THREE_DIMS
        assert store[key].read().shape == (2, 16, 16)


def test_pyramid_reads_at_full_resolution(
    client: Container, pyramid_store: Path
) -> None:
    node = register_image(client, "image", pyramid_store.as_uri() + "/det")

    assert node.read().shape == (2, 16, 16)


@pytest.mark.parametrize(
    ("store", "logged"),
    [
        ("bioformats2raw_store", "Bf2Raw"),
        ("malformed_store", "failed validation"),
    ],
)
def test_unsupported_group_is_served_as_plain_zarr_and_logged(
    request: pytest.FixtureRequest,
    caplog: pytest.LogCaptureFixture,
    store: str,
    logged: str,
) -> None:
    path: Path = request.getfixturevalue(store)
    with caplog.at_level(logging.INFO, logger="ome_tiled"):
        adapter = OmeZarrAdapter.from_uris(path.as_uri())

    assert adapter.structure_family == StructureFamily.container
    assert list(adapter) == ["0"]
    assert logged in caplog.text


@pytest.mark.usefixtures("acquire_zarr_store", "ome_writers_acquire_zarr_store")
def test_detection_hook_routes_every_ome_zarr_store(
    client: Container, data_dir: Path
) -> None:
    anyio.run(
        lambda: register(
            client,
            data_dir,
            adapters_by_mimetype={OME_ZARR_MIMETYPE: OmeZarrAdapter},
            mimetype_detection_hook="ome_tiled:detect",
        )
    )

    assert client["run"]["det"].structure().dims == THREE_DIMS
    assert client["acquire"].structure().dims == FOUR_DIMS


@pytest.mark.usefixtures("acquire_zarr_store", "ome_writers_acquire_zarr_store")
def test_extension_route_misses_a_store_named_zarr(
    client: Container, data_dir: Path
) -> None:
    anyio.run(
        lambda: register(
            client,
            data_dir,
            adapters_by_mimetype={OME_ZARR_MIMETYPE: OmeZarrAdapter},
            mimetypes_by_file_ext={".ome.zarr": OME_ZARR_MIMETYPE},
        )
    )

    assert client["acquire"].structure().dims == FOUR_DIMS
    assert client["run"]["det"]["0"].structure().dims is None


def test_embedded_server_reads_images_once_the_adapter_is_inserted(
    embedded_server: SimpleTiledServer, ome_writers_acquire_zarr_store: Path
) -> None:
    embedded_server.catalog.context.adapters_by_mimetype.maps[0][OME_ZARR_MIMETYPE] = (
        OmeZarrAdapter
    )
    client = from_uri(embedded_server.uri)

    node = register_image(client, "image", ome_writers_acquire_zarr_store.as_uri())

    assert node.structure().dims == FOUR_DIMS
    assert node.read().shape == (2, 3, 8, 8)
