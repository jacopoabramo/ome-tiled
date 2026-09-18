[![PyPI](https://img.shields.io/pypi/v/ome-tiled.svg?color=green)](https://pypi.org/project/ome-tiled)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ome-tiled)](https://pypi.org/project/ome-tiled)
[![codecov](https://codecov.io/gh/redsun-acquisition/ome-tiled/graph/badge.svg)](https://codecov.io/gh/redsun-acquisition/ome-tiled)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# ome-tiled

An adapter for [`tiled`](https://github.com/bluesky/tiled) that serves OME-Zarr
images as arrays with their axis names, which `tiled`'s own Zarr adapter
leaves out.

## Install

With `uv` (recommended):

```console
uv add ome-tiled
```

With `pip`:

```console
pip install ome-tiled
```

Install it on the server, and also wherever `tiled register` runs: registering
opens each store through the adapter on the registering side.

To write Bluesky runs into a catalog with `bluesky-tiled-plugins`, install the
`bluesky` extra: `uv add "ome-tiled[bluesky]"`.

## Usage

Serve a directory, letting `ome-tiled` find the OME-Zarr stores in it:

```console
tiled serve directory data/ \
    --adapter application/x-ome-zarr=ome_tiled:OmeZarrAdapter \
    --mimetype-hook ome_tiled:detect
```

Each image then reads as one array whose `dims` are its axis names:

```python
from tiled.client import from_uri

client = from_uri("http://localhost:8000", api_key="...")
client["stack"].structure().dims  # ('t', 'z', 'y', 'x')
```

The hook recognizes a store by its metadata, whatever it is called. Stores
named `*.ome.zarr` can be routed by name instead, with
`--ext .ome.zarr=application/x-ome-zarr` in place of `--mimetype-hook`.

### From a configuration file

Register the adapter in the server's configuration:

```yaml
# config.yml
trees:
  - tree: catalog
    path: /
    args:
      uri: ./catalog.db
      init_if_not_exists: true
      readable_storage:
        - data/
      adapters_by_mimetype:
        application/x-ome-zarr: ome_tiled:OmeZarrAdapter
```

Then start the server and register the directory:

```console
tiled serve config config.yml --api-key secret
tiled register http://localhost:8000 data/ --api-key secret \
    --adapter application/x-ome-zarr=ome_tiled:OmeZarrAdapter \
    --mimetype-hook ome_tiled:detect
```

### From Python

```python
from tiled.catalog import from_uri

catalog = from_uri(
    "catalog.db",
    readable_storage=["data/"],
    init_if_not_exists=True,
    adapters_by_mimetype={"application/x-ome-zarr": "ome_tiled:OmeZarrAdapter"},
)
```

`tiled.server.simple.SimpleTiledServer` takes no adapters, so add the adapter to
its catalog after starting the server and before registering anything:

```python
from tiled.server.simple import SimpleTiledServer

from ome_tiled import OME_ZARR_MIMETYPE, OmeZarrAdapter

server = SimpleTiledServer(readable_storage=["data/"])
server.catalog.context.adapters_by_mimetype.maps[0][OME_ZARR_MIMETYPE] = OmeZarrAdapter
```

### Registering by hand

`tiled` answers a registered node's structure and metadata from its database,
so a registration made with `client.new` has to store the adapter's own, or the
node reads without its axis names:

```python
from tiled.structures.core import StructureFamily
from tiled.structures.data_source import Asset, DataSource, Management

from ome_tiled import OME_ZARR_MIMETYPE, OmeZarrAdapter

uri = "file:///data/stack.ome.zarr"
adapter = OmeZarrAdapter.from_uris(uri)
client.new(
    key="stack",
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
```

The URI may name the image group or its full-resolution array; both read the
same way.

### Writing runs with `TiledWriter`

`bluesky-tiled-plugins`' `TiledWriter` registers each data key of a run from its
`StreamResource` document, with a structure computed from the documents: the
number of rows times the shape of each. A detector writing a multidimensional
OME-Zarr store frame by frame describes a stack of frames, which is not the
shape of the store, and the node cannot be read. Registering the consolidator
this package provides makes `TiledWriter` store the image as the store holds
it, with its shape, chunks and axis names:

```python
from bluesky import RunEngine
from bluesky_tiled_plugins import TiledWriter
from tiled.client import from_uri

from ome_tiled.bluesky import register_consolidator

register_consolidator()
RE = RunEngine()
RE.subscribe(TiledWriter(from_uri("http://localhost:8000", api_key="...")))
```

The detector's `StreamResource` gives `application/x-ome-zarr` as the mimetype
and the store, or its image, as the URI. The server needs `OmeZarrAdapter`
registered for that mimetype, as above.

## What it reads

- NGFF 0.4 and 0.5 images and label images, validated with
  [`yaozarrs`](https://github.com/imaging-formats/yaozarrs). The axes, with their
  types and units, are under `axes` in the node's metadata.
- A Zarr group holding several such images, each presented as its own array.
- The full-resolution level only. Pyramids read at level `0`.

Anything else is served as `tiled`'s Zarr adapter serves it, with a log line
saying why: other NGFF layouts such as `bioformats2raw` series, plates, wells
and label groups, and any group whose NGFF metadata fails validation.
Validation is strict, so a file that breaks the NGFF specification, for example
a dataset without `coordinateTransformations`, reads as plain Zarr rather than
as an image.

Axes of a custom kind, such as a scan pattern, keep their names too. NGFF
orders axes as time, then channel or custom, then space, so a file that puts a
custom axis after the spatial ones fails validation and reads as plain Zarr.

## More

The `tiled` documentation explains adapters, mimetypes and detection hooks in
more detail: [Serve Files with Custom Formats](https://blueskyproject.io/tiled/user-guide/read-custom-formats.html).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
