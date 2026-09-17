from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import acquire_zarr as az
import numpy as np
import ome_writers as ow
import pytest
import zarr
from tiled.catalog import in_memory
from tiled.client import Context, from_context
from tiled.server.app import build_app

from ome_tiled import OME_ZARR_MIMETYPE, OmeZarrAdapter

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from tiled.client.container import Container

FOUR_AXES = [
    {"name": "t", "type": "time"},
    {"name": "z", "type": "space", "unit": "micrometer"},
    {"name": "y", "type": "space"},
    {"name": "x", "type": "space"},
]
DATASETS = [
    {"path": "0", "coordinateTransformations": [{"type": "scale", "scale": [1] * 4}]}
]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    return path


@pytest.fixture
def client(tmp_path: Path, data_dir: Path) -> Iterator[Container]:
    catalog = in_memory(
        writable_storage=str(tmp_path / "writable"),
        readable_storage=[str(data_dir)],
        adapters_by_mimetype={OME_ZARR_MIMETYPE: OmeZarrAdapter},
    )
    with Context.from_app(build_app(catalog)) as context:
        yield from_context(context)


@pytest.fixture
def ome_writers_acquire_zarr_store(data_dir: Path) -> Path:
    return write_ome_writers(data_dir / "acquire", "acquire-zarr")


@pytest.fixture
def ome_writers_zarr_python_store(data_dir: Path) -> Path:
    return write_ome_writers(data_dir / "python", "zarr-python")


@pytest.fixture
def acquire_zarr_store(data_dir: Path) -> Path:
    return write_acquire_zarr(data_dir / "run.zarr", ("det", "det_median"), 0)


@pytest.fixture
def pyramid_store(data_dir: Path) -> Path:
    return write_acquire_zarr(data_dir / "pyramid.zarr", ("det",), 1)


@pytest.fixture
def ngff04_store(data_dir: Path) -> Path:
    multiscale = {"version": "0.4", "axes": FOUR_AXES, "datasets": DATASETS}
    return write_by_hand(data_dir / "v04.zarr", 2, {"multiscales": [multiscale]})


@pytest.fixture
def ngff05_store(data_dir: Path) -> Path:
    multiscale = {"axes": FOUR_AXES, "datasets": DATASETS}
    attributes = {"ome": {"version": "0.5", "multiscales": [multiscale]}}
    return write_by_hand(data_dir / "v05.zarr", 3, attributes)


@pytest.fixture
def malformed_store(data_dir: Path) -> Path:
    multiscale = {"axes": FOUR_AXES, "datasets": [{"path": "0"}]}
    attributes = {"ome": {"version": "0.5", "multiscales": [multiscale]}}
    return write_by_hand(data_dir / "malformed.zarr", 3, attributes)


@pytest.fixture
def bioformats2raw_store(data_dir: Path) -> Path:
    path = data_dir / "series.zarr"
    root = zarr.open_group(path, mode="w", zarr_format=3)
    root.attrs.update({"ome": {"version": "0.5", "bioformats2raw.layout": 3}})
    root.create_array("0", shape=(2, 3, 8, 8), dtype="uint16")[:] = 1
    return path


def write_ome_writers(
    root: Path, backend: Literal["acquire-zarr", "zarr-python"]
) -> Path:
    settings = ow.AcquisitionSettings(
        root_path=str(root),
        dtype="uint16",
        dimensions=(
            ow.Dimension(name="t", count=2, type="time", chunk_size=1),
            ow.Dimension(
                name="z", count=3, type="space", unit="micrometer", chunk_size=1
            ),
            ow.Dimension(name="y", count=8, type="space", chunk_size=8),
            ow.Dimension(name="x", count=8, type="space", chunk_size=8),
        ),
        format=ow.OmeZarrFormat(backend=backend),
    )
    stream = ow.create_stream(settings)
    for _ in range(6):
        stream.append(np.full((8, 8), 1, "uint16"))
    stream.close()
    return root.with_name(root.name + ".ome.zarr")


def write_by_hand(
    path: Path, zarr_format: Literal[2, 3], attributes: dict[str, Any]
) -> Path:
    group = zarr.open_group(path, mode="w", zarr_format=zarr_format)
    group.attrs.update(attributes)
    group.create_array("0", shape=(2, 3, 8, 8), dtype="uint16")[:] = 1
    return path


def write_acquire_zarr(path: Path, keys: tuple[str, ...], max_levels: int) -> Path:
    arrays = []
    for key in keys:
        settings = az.ArraySettings()
        settings.output_key = key
        settings.data_type = az.DataType.UINT16
        settings.is_ngff = True
        settings.max_levels = max_levels
        settings.dimensions = [
            dimension("t", az.DimensionType.TIME, 0, 1),
            dimension("y", az.DimensionType.SPACE, 16, 16),
            dimension("x", az.DimensionType.SPACE, 16, 16),
        ]
        arrays.append(settings)
    stream_settings = az.StreamSettings()
    stream_settings.store_path = str(path)
    stream_settings.arrays = arrays
    stream = az.ZarrStream(stream_settings)
    for _ in range(2):
        for key in keys:
            stream.append(np.full((16, 16), 1, "uint16"), key=key)
    del stream
    return path


def dimension(name: str, kind: az.DimensionType, size: int, chunk: int) -> az.Dimension:
    return az.Dimension(
        name=name,
        kind=kind,
        array_size_px=size,
        chunk_size_px=chunk,
        shard_size_chunks=1,
    )
