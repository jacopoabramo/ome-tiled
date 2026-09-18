from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, Any

import pytest
from tiled.utils import import_object

import ome_tiled
from ome_tiled import OME_ZARR_MIMETYPE, detect
from ome_tiled._ngff import NgffImage, NgffSkipped, classify

if TYPE_CHECKING:
    from pathlib import Path

AXES = [
    {"name": "t", "type": "time"},
    {"name": "z", "type": "space", "unit": "micrometer"},
    {"name": "y", "type": "space"},
    {"name": "x", "type": "space"},
]
DATASETS = [
    {
        "path": "0",
        "coordinateTransformations": [{"type": "scale", "scale": [1, 1, 1, 1]}],
    }
]
IMAGE_04 = {"version": "0.4", "axes": AXES, "datasets": DATASETS}
IMAGE_05 = {"axes": AXES, "datasets": DATASETS}
EXPECTED = NgffImage(dims=("t", "z", "y", "x"), axes=tuple(AXES), path="0")

# written out rather than read from __all__, so a name dropped from the package
# fails here instead of leaving nothing to parametrize
CONFIGURATION_STRINGS = [
    "ome_tiled:OME_ZARR_MIMETYPE",
    "ome_tiled:OmeZarrAdapter",
    "ome_tiled:detect",
]


@pytest.mark.parametrize("path", CONFIGURATION_STRINGS)
def test_configuration_strings_resolve_through_the_package(path: str) -> None:
    name = path.partition(":")[2]
    assert import_object(path) is getattr(ome_tiled, name)


def test_the_package_imports_without_the_bluesky_extra() -> None:
    """Only ``ome_tiled.bluesky`` needs ``bluesky-tiled-plugins``."""
    code = "import sys, ome_tiled; assert 'bluesky_tiled_plugins' not in sys.modules"

    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize(
    "attributes",
    [
        {"multiscales": [IMAGE_04]},
        {"ome": {"version": "0.5", "multiscales": [IMAGE_05]}},
        {"multiscales": [IMAGE_04], "image-label": {"version": "0.4"}},
        {"ome": {"version": "0.5", "multiscales": [IMAGE_05], "image-label": {}}},
    ],
    ids=["image-0.4", "image-0.5", "label-image-0.4", "label-image-0.5"],
)
def test_images_are_read_in_both_versions(attributes: dict[str, Any]) -> None:
    assert classify(attributes) == EXPECTED


@pytest.mark.parametrize(
    ("attributes", "reason"),
    [
        ({"bioformats2raw.layout": 3}, "Bf2Raw"),
        ({"ome": {"version": "0.5", "labels": ["cells"]}}, "LabelsGroup"),
        (
            {
                "ome": {
                    "version": "0.5",
                    "multiscales": [{"axes": AXES, "datasets": [{"path": "0"}]}],
                }
            },
            "coordinateTransformations",
        ),
        ({"ome": {"version": "0.5"}}, "validation"),
    ],
    ids=["bioformats2raw", "labels-group", "image-without-transforms", "empty-ome"],
)
def test_other_ngff_groups_are_skipped_with_a_reason(
    attributes: dict[str, Any], reason: str
) -> None:
    result = classify(attributes)

    assert isinstance(result, NgffSkipped)
    assert reason in result.reason


@pytest.mark.parametrize("attributes", [{}, {"foo": 1}], ids=["empty", "unrelated"])
def test_plain_groups_are_not_ngff(attributes: dict[str, Any]) -> None:
    assert classify(attributes) is None


@pytest.mark.parametrize(
    "store",
    [
        "ome_writers_acquire_zarr_store",
        "acquire_zarr_store",
        "ngff04_store",
        "ngff05_store",
        "bioformats2raw_store",
    ],
)
def test_ome_zarr_stores_are_detected(
    request: pytest.FixtureRequest, store: str
) -> None:
    path: Path = request.getfixturevalue(store)

    assert detect(path, "application/x-zarr") == OME_ZARR_MIMETYPE


@pytest.mark.parametrize(
    ("target", "mimetype"),
    [
        ("plain_zarr_store", "application/x-zarr"),
        ("plain_directory", None),
        ("text_file", "text/csv"),
    ],
)
def test_anything_else_keeps_its_mimetype(
    request: pytest.FixtureRequest, target: str, mimetype: str | None
) -> None:
    path: Path = request.getfixturevalue(target)

    assert detect(path, mimetype) == mimetype
