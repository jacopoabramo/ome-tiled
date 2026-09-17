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

For a catalog built in Python, register the adapter under its mimetype:

```python
from tiled.catalog import from_uri

catalog = from_uri(
    "catalog.db",
    readable_storage=["data/"],
    init_if_not_exists=True,
    adapters_by_mimetype={"application/x-ome-zarr": "ome_tiled:OmeZarrAdapter"},
)
```

The `tiled` documentation explains adapters, mimetypes and detection hooks in
more detail: [Serve Files with Custom Formats](https://blueskyproject.io/tiled/user-guide/read-custom-formats.html).

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
