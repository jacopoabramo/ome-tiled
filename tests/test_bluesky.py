from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from bluesky_tiled_plugins import TiledWriter
from bluesky_tiled_plugins.writing.consolidators import CONSOLIDATOR_REGISTRY
from event_model import compose_run, compose_stream_resource
from tiled.catalog import in_memory
from tiled.client import Context, from_context
from tiled.server.app import build_app

from ome_tiled import OME_ZARR_MIMETYPE, OmeZarrAdapter
from ome_tiled.bluesky import register_consolidator

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from tiled.client.container import Container

FOUR_DIMS = ("t", "z", "y", "x")


@pytest.fixture
def registry() -> Iterator[None]:
    """Restore the consolidators ``TiledWriter`` knows after the test."""
    saved = dict(CONSOLIDATOR_REGISTRY)
    yield
    CONSOLIDATOR_REGISTRY.clear()
    CONSOLIDATOR_REGISTRY.update(saved)


@pytest.fixture
def run_client(tmp_path: Path, data_dir: Path) -> Iterator[Container]:
    """Yield a client of a catalog holding event tables and serving OME-Zarr images."""
    catalog = in_memory(
        writable_storage=[
            str(tmp_path / "writable"),
            f"duckdb:///{(tmp_path / 'events.duckdb').as_posix()}",
        ],
        readable_storage=[str(data_dir)],
        adapters_by_mimetype={OME_ZARR_MIMETYPE: OmeZarrAdapter},
    )
    with Context.from_app(build_app(catalog)) as context:
        yield from_context(context)


def write_run(
    client: Container, uri: str, row_shape: tuple[int, ...], rows: int
) -> str:
    """Write a run through ``TiledWriter`` whose one data key is the store at *uri*."""
    writer = TiledWriter(client)
    bundle = compose_run()
    writer("start", bundle.start_doc)
    data_key: dict[str, Any] = {
        "source": "camera",
        "dtype": "array",
        "shape": list(row_shape),
        "dtype_numpy": "<u2",
        "external": "STREAM:",
    }
    descriptor = bundle.compose_descriptor(name="primary", data_keys={"det": data_key})
    writer("descriptor", descriptor.descriptor_doc)
    resource = compose_stream_resource(
        mimetype=OME_ZARR_MIMETYPE,
        uri=uri,
        data_key="det",
        parameters={"chunk_shape": [1, *row_shape]},
        start=bundle.start_doc,
    )
    writer("stream_resource", resource.stream_resource_doc)
    for row in range(rows):
        writer(
            "stream_datum",
            resource.compose_stream_datum(
                indices={"start": row, "stop": row + 1},
                descriptor=descriptor.descriptor_doc,
            ),
        )
    writer("stop", bundle.compose_stop())
    return str(bundle.start_doc["uid"])


@pytest.mark.usefixtures("registry")
@pytest.mark.parametrize(
    ("row_shape", "rows"),
    [((8, 8), 6), ((3, 8, 8), 2)],
    ids=["a-frame-per-row", "a-z-stack-per-row"],
)
def test_the_run_stores_the_image_as_the_store_holds_it(
    run_client: Container,
    ome_writers_acquire_zarr_store: Path,
    row_shape: tuple[int, ...],
    rows: int,
) -> None:
    register_consolidator()

    uid = write_run(
        run_client, ome_writers_acquire_zarr_store.as_uri(), row_shape, rows
    )
    det = run_client[uid]["primary"]["det"]

    assert det.structure().shape == (2, 3, 8, 8)
    assert det.structure().dims == FOUR_DIMS
    assert det.read().sum() == 2 * 3 * 8 * 8
    assert run_client[uid]["primary"].read()["det"].dims == FOUR_DIMS
