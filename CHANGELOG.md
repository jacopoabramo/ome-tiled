# Changelog

## Unreleased

### Added

- `OME_ZARR_MIMETYPE` (`ome_tiled`): the mimetype, `application/x-ome-zarr`,
  under which a catalog routes OME-Zarr data to `OmeZarrAdapter`.
- `OmeZarrAdapter` (`ome_tiled`): a `tiled` adapter serving an NGFF 0.4 or 0.5
  image, registered by its group or by its full-resolution array, as one array
  whose `dims` are the axes' names, with the axes under `axes` in the metadata.
  A group holding images presents each as such an array; any other group is
  served as `tiled`'s Zarr adapter serves it.

  ```python
  catalog_from_uri(
      ...,
      adapters_by_mimetype={"application/x-ome-zarr": "ome_tiled:OmeZarrAdapter"},
  )
  ```
