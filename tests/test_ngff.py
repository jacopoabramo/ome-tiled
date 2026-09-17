from __future__ import annotations

from typing import Any

import pytest
from tiled.utils import import_object

import ome_tiled
from ome_tiled._ngff import NgffImage, NgffSkipped, classify

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
CONFIGURATION_STRINGS = ["ome_tiled:OME_ZARR_MIMETYPE", "ome_tiled:OmeZarrAdapter"]


@pytest.mark.parametrize("path", CONFIGURATION_STRINGS)
def test_configuration_strings_resolve_through_the_package(path: str) -> None:
    name = path.partition(":")[2]
    assert import_object(path) is getattr(ome_tiled, name)


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
