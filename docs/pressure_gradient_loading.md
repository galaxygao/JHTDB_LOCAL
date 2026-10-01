# Pressure gradient acquisition

Run from the project root using the existing Python environment and pipeline
configuration. Your personal token is resolved by the existing authentication
code (environment first, then the configured token file). There is no public
testing-token fallback or 4096-point network batching in this downloader.

```powershell
# Small online check: 8^3 points, same stored frame as the velocity cache.
.\.venv\Scripts\python.exe -m jhtdb_pipeline smoke --time-index 1 --field pressure_gradient

# Download/resume just the missing pressure-gradient data.
.\.venv\Scripts\python.exe -m jhtdb_pipeline cache --time-index 1 --field pressure_gradient

# Download/resume velocity and pressure gradient in sequence.
.\.venv\Scripts\python.exe -m jhtdb_pipeline cache --time-index 1 --with-pressure-gradient

# Include pressure-gradient acquisition in the existing processing workflow.
.\.venv\Scripts\python.exe -m jhtdb_pipeline single-frame --time-index 1 --with-pressure-gradient

.\.venv\Scripts\python.exe -m jhtdb_pipeline validate-input --time-index 1 --field pressure_gradient
.\.venv\Scripts\python.exe -m jhtdb_pipeline status --field pressure_gradient
```

The field selector defaults to `velocity`, preserving existing commands.
The default `status` also includes `pressure_gradient_inputs` beside velocity
inputs and processed results. Both PowerShell workflow wrappers accept
`-WithPressureGradient` to pass this option to `single-frame`.
Pressure gradients use Giverny `getData(cube, 'pressure', physical_time,
'none', 'fd4noint', 'gradient', points)`. These are server-computed fourth-order
finite differences at grid points. They are not local FFT derivatives.
Physical time is `(time_index-1)*stored_time_step`; coordinates are zero-based
grid indices times `domain_length/grid_shape`. The last periodic endpoint is
excluded, matching velocity cutouts.

## Storage and provenance

```text
state/
  inputs/t000001/
    velocity_cache.zarr/velocity                 (3,z,y,x)
    pressure_gradient_cache.zarr/pressure_gradient (3,z,y,x)
    strain_cache.zarr/sij_sij
  catalog.sqlite                                existing velocity ledger
  pressure_gradient_catalog.sqlite              same ledger schema, separate field
  manifests/pressure_gradient/input_t000001.json
  qa/pressure_gradient/input_t000001.json
```

Gradient components are `dPdx,dPdy,dPdz`, for JHTDB kinematic pressure `P=p/rho`.
Dataset, frame, physical time, grid shape, component order, operator, derivative
method, checksums, and validation status are persisted. Existing velocity
manifest hashes and processed results are not changed by pressure acquisition.
Velocity gradients remain in `results/t000001_shared/center_raw.zarr/gradient`
with their existing center-crop scope and spectral differentiation provenance.

All network requests share the existing `jhtdb-request.lock`. Pressure requests
use 128x128x64 grid-point blocks (1048576 points), one request at a time, with
existing retry/backoff settings. Each block is sent in one getData call, subject
to the server's advertised max_data_points limit. Storage/checksum chunks remain
16^3 for compatibility with existing caches and resume ledgers. Each completed
chunk is read back and SHA-256 verified. Reruns skip fully verified request
blocks; partially missing or corrupted blocks are downloaded again, writing
only the pending checksum chunks. A validated
manifest is written only after complete coverage and finite-value validation.
The complete 1024^3 field needs 1024 requests before retries (256 times fewer
than the previous 16^3 request scheme) and 12 GiB uncompressed; full
acquisition can be slow. `smoke` is the small online check, not a full download.

## Aligned reads and analysis

```python
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.input_fields import open_frame_fields
cfg = load_config('configs/pipeline.yaml')
fields = open_frame_fields(cfg, 1)
velocity = fields['velocity']                  # lazy Zarr arrays
pressure_gradient = fields['pressure_gradient']
```

The loader checks that both stores are validated and have matching dataset,
time, grid, and axis metadata. The existing `open_complete_result` continues to
provide velocity and velocity-gradient center crops. Apply the same crop to
pressure gradients when comparing to those result arrays.

`qpower_analysis/config.example.json` now points to the pressure-gradient cache.
After acquisition and validation, run its preflight before analysis. No live
download was performed while implementing this change; network behavior is
covered by mocked responses and requires the online smoke check with your token.

Official derivative-method reference:
https://turbulence.pha.jhu.edu/analysisdoc.aspx
