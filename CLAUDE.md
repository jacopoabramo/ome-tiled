# ome-tiled agent & contributor conventions

Single source of conventions for agents (Claude, Copilot) and contributors:
cross-link, don't duplicate.

## Repository layout

```text
ome-tiled/
|-- src/ome_tiled/
|   |-- __init__.py      the hub: re-exports and __all__, defines nothing
|   |-- py.typed
|   |-- _ngff.py         OME_ZARR_MIMETYPE, reading multiscales, detect
|   |-- _adapter.py      OmeZarrAdapter
|   `-- bluesky.py       OmeZarrConsolidator, register_consolidator (bluesky extra)
|-- tests/
|   |-- conftest.py      in-process catalog, hand-written NGFF 0.4 and 0.5 stores
|   |-- test_ngff.py     format rules, no tiled server involved
|   |-- test_adapter.py  registration and reading through a catalog
|   `-- test_bluesky.py  runs written through TiledWriter
|-- .github/workflows/   CI: code analysis, tests, release
|-- .claude/             agents, commands, settings
|-- pyproject.toml       dependencies and all tool config: ruff, mypy, pytest, coverage, tox
|-- prek.toml            git hooks: file checks, ruff
|-- README.md            usage, registration, detection, limits
|-- CHANGELOG.md
|-- CODE_OF_CONDUCT.md
|-- LICENSE              Apache License 2.0
`-- uv.lock
```

## Build & validate

`tox` is the entry point, configured under `[tool.tox]` in `pyproject.toml`.
Every environment installs from `uv.lock` through `tox-uv-bare`, so a local run
uses the versions CI resolves rather than whatever the project `.venv`
accumulated. The plugin is `tox-uv-bare` rather than `tox-uv` so that the `uv`
it drives is the one on `PATH`: `tox-uv` depends on the `uv` package, which puts
a second `uv.exe` in the project `.venv` and shadows the installed one:

```bash
uv run tox                                   # lint, mypy, tests
uv run tox -e tests                          # one environment
uv run tox -e tests -- tests/test_ngff.py -x # posargs reach pytest
```

| environment | what it runs |
| --- | --- |
| `lint` | `ruff check --fix` then `ruff format` |
| `mypy` | `mypy` |
| `tests` | `pytest -q` |

**Run what the change can break, not the whole matrix.** A change confined to
`README.md` or `CHANGELOG.md` breaks nothing `tox` checks. A change to
docstrings runs `lint`, since ruff's `D` rules check them. Anything touching
code or tests runs the full `uv run tox`.

The project `.venv` still works for a quick loop (`uv run pytest -q`), but it
is not authoritative: it holds every group any `uv sync` has installed. Trust
tox.

- mypy is `strict = true` with `warn_unreachable`; `files = "."`, so **tests
  are strictly type-checked too**. `tiled` ships no `py.typed`, so everything
  imported from it is `Any`; the adapter's class line is the one place that
  needs `# type: ignore[misc]`, and it says why. Only `import-untyped` and
  `no-untyped-call` are globally disabled; do not widen that list to silence a
  real error.
- Tests are synchronous, since `tiled`'s in-process client is, so there is no
  `asyncio_mode` and no async test.

## Architecture invariants

- **Standalone.** The package depends on `tiled[server]`, `zarr` and
  `yaozarrs`, and on nothing written for a particular application. `pydantic`
  arrives through `yaozarrs` and is not declared. The `bluesky` extra adds
  `bluesky-tiled-plugins`, needed only by `ome_tiled.bluesky`. No import, name,
  fixture or example refers to an application.
- **Three public names**, `OME_ZARR_MIMETYPE`, `OmeZarrAdapter` and
  `detect`, re-exported by `__init__.py`. Every module is private. `tiled`
  imports configuration strings with `import_object`, which resolves
  `ome_tiled:OmeZarrAdapter` and `ome_tiled:detect` through the package, so no
  module needs to be public for a server configuration to reach it.
- **`ome_tiled.bluesky` is the one public module.** It imports
  `bluesky-tiled-plugins`, which the package must not need, so `__init__.py`
  cannot re-export it. `import ome_tiled` never imports it, and
  `test_ngff.py` checks that in a fresh interpreter.
- **`_ngff.py` imports nothing from `tiled`.** The format rules live there,
  built on `yaozarrs`, and are tested without a catalog. `detect` lives there because it is a format
  question.
- **An image is a group `yaozarrs` validates as an image or label image**,
  NGFF 0.4 or 0.5. A registration naming the image group and one naming its
  `0` array read the same way, as one array whose `dims` are the axes' names,
  at level `0`, with the axes under `axes` in the metadata.
- **Everything else passes through untouched.** Every other NGFF layout
  `yaozarrs` recognizes, and every group whose NGFF metadata fails validation,
  goes to `ZarrGroupAdapter` as it would without this package, with a log line
  saying why. Validation is strict on purpose: never guess at a malformed file.
- **A catalog node keeps what was stored at registration.** `tiled` serves a
  registered node's structure and metadata from its database, not from the
  adapter. `tiled register` stores the adapter's own; anyone registering by
  hand stores `OmeZarrAdapter.from_uris(uri).structure()` and `.metadata()`,
  or the node reads without `dims`.
- **The adapter never writes.** It inherits `ZarrGroupAdapter`'s read-only
  behaviour; nothing here adds `write`, `write_block` or `patch`.

## Code conventions

- Python >=3.11, `from __future__ import annotations` everywhere (ruff
  `FA102`).
- Ruff lint has `D` (numpy docstring convention), `I` and `TC` (type-check
  imports) enabled: runtime-unneeded imports go under `if TYPE_CHECKING:`.
  Public symbols need docstrings; `D100`/`D104` are ignored.
- Private modules are `_underscored`; `__init__.py` re-exports the public
  surface with an explicit `__all__`. Add new public symbols to both.
- **The underscore marks what `__all__` cannot.** A module named `_foo.py` is
  private in its entirety, so its **module-level members carry no underscore**:
  the module name already said it. **Class members always keep the
  underscore**, because `__all__` is module-scoped and can never say that a
  method is private, and a reader's autocomplete keys on the name. Ruff `D103`
  treats a non-underscore function as public, so functions in a private module
  need docstrings.
- Public methods are named in the imperative: `read`, `detect`, not `reading`
  or `detection`. Nouns are for what a method returns or holds, which are
  properties. Deviate only where an external convention requires it, as
  `tiled`'s adapter interface does.
- **`@property` is for public API only.** Private state is a plain attribute,
  computed once where it is first known; private behaviour is an ordinary
  underscored method.
- **Don't alias an attribute to a local for a single use.** A local earns its
  place when the value is read several times and reaching it costs something,
  when a type checker needs the narrowing, or when repeating the expression
  would hide the line.
- **No comments in the import block.** Not above an import, not above a group,
  and not to explain a `# noqa`. If a runtime import is surprising, say why at
  the annotation that needs it.
- Public API change -> docstring + `CHANGELOG.md` entry.

### Docstrings and comments

- Docstrings are concise and minimal: only the behaviour of the thing being
  defined, scoped to that definition. Write for a reader who has nothing but
  the docstring: no design documents, no history of previous designs.
- Don't restate the signature in prose, and don't document parameters whose
  meaning the name and type already carry. A `Parameters`, `Returns` or
  `Raises` section earns its place when it says something the signature cannot:
  accepted values, what `None` means, which exception and when.
- No section-divider or banner comments, and no comment blocks describing the
  code that follows. A comment earns its place only by explaining why a
  specific statement is the way it is.

## Testing conventions

- Tests are flat under `tests/`, one module per private module. Shared fixtures
  belong in `conftest.py`.
- **Every reading behaviour is tested on real layouts and both NGFF
  versions**: stores written by `ome-writers` with its `acquire-zarr` and
  `zarr-python` backends, one written by `acquire-zarr` with `is_ngff=True`
  and two keys, and hand-written 0.4 and 0.5 fixtures carrying
  `coordinateTransformations`, plus one without them that must read as plain
  Zarr. Each image is registered once by group path and once by array path.
- A store fixture named in a parametrize list is fetched with
  `request.getfixturevalue`, which cannot resolve a parametrized fixture: give
  each variant its own fixture.
- **Test objects go at the top of the module, after the imports**: fixtures and
  helpers, before the first test. A test body is then the case it exercises
  and nothing else.
- **All imports live at the top of the module**, in tests too.
- Prefer the public interface: register through a catalog and read through a
  client, and assert on what the client sees.
- Parametrize normal and edge cases together in one `@pytest.mark.parametrize`.
- **Falsify a test before trusting it.** A test asserting `dims` must fail
  with this package's adapter replaced by `tiled`'s `ZarrAdapter`: in
  `adapters_by_mimetype` for a group path, where the adapter opens the image at
  read time, and in the registration for an array path, where only the stored
  structure carries the names.
- A property only a type checker can observe is tested in `tests/typing/` with
  `typing.assert_type`, in a module pytest never collects.

## Docs conventions

There is no docs site. The README carries usage, registration, detection and
limits.

- **Examples are agnostic.** Every snippet and configuration fragment is
  written for a reader who has only this repository: plain file paths, `tiled`
  commands, no application or plugin names.
- **Library and package names are code spans**: `` `ome-tiled` ``,
  `` `tiled` ``, `` `zarr` ``, `` `acquire-zarr` ``, at every mention.
  Docstrings do the same with double backticks. Headings, link text and a name
  inside a code block stay as they are.

## Response style (agents)

- Terse. No preamble, no restatement of the request, no summary of what you
  just did.
- Show diffs, not whole files. Don't explain code unless asked.
- Don't narrate intent ("I'll now..."); just make the change.
- State assumptions in one line; ask only when genuinely blocked.
- No em dashes and no en dashes, anywhere: chat, commits, docs, docstrings,
  comments, PR and issue text. Use a plain hyphen or restructure. Arrows are
  `->` and `<-`, never `→` or `⇒`.
- `.claude/agents/*` files stay slim: scope, verify commands, and pointers to
  this file. Never restate invariants there; cross-link instead.

## Updating this guide

Say **"Update CLAUDE.md with..."** to persist a convention here. Durable,
shareable rules belong in this file, not in per-session memory.
