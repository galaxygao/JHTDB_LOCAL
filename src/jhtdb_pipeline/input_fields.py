"""Field-specific paths sharing the existing acquisition and validation code."""
import zarr


class PressureGradientConfig:
    variable = "pressure_gradient"
    components = ["dPdx", "dPdy", "dPdz"]
    acquisition_metadata = {
        "source": "JHTDB getData", "source_variable": "pressure",
        "spatial_operator": "gradient", "spatial_method": "fd4noint",
        "temporal_method": "none", "pressure_definition": "JHTDB kinematic pressure P=p/rho",
    }

    def __init__(self, base):
        self.base = base
        self.tile_shape = tuple(min(16, n) for n in base.grid_shape)
        if any(n % t for n, t in zip(base.grid_shape, self.tile_shape)):
            raise ValueError("pressure-gradient grid must be divisible by tile dimensions")
        # Network batches are independent of the existing 16^3 checksum chunks.
        # Keeping chunk boundaries unchanged preserves old catalogs and caches.
        self.request_shape = tuple(min(limit, n) for limit, n in zip((128, 128, 64), base.grid_shape))

    def __getattr__(self, name):
        return getattr(self.base, name)

    @property
    def catalog_path(self):
        return self.base.state_root / "pressure_gradient_catalog.sqlite"

    @property
    def manifest_path(self):
        return self.base.manifest_path / "pressure_gradient"

    @property
    def qa_path(self):
        return self.base.qa_path / "pressure_gradient"

    def raw_store_path(self, time_index):
        return self.base.persistent_input_path(time_index) / "pressure_gradient_cache.zarr"


def field_config(cfg, field):
    if field == "velocity":
        return cfg
    if field == "pressure_gradient":
        return PressureGradientConfig(cfg)
    raise ValueError(f"unsupported input field: {field}")


def open_frame_fields(cfg, time_index):
    """Open aligned validated full-domain fields lazily, without loading arrays."""
    fields = {}
    for name in ("velocity", "pressure_gradient"):
        view = field_config(cfg, name)
        root = zarr.open_group(str(view.raw_store_path(time_index)), mode="r")
        expected = {
            "status": "validated", "dataset": cfg.dataset,
            "time_index": time_index, "physical_time": cfg.physical_time(time_index),
            "grid_shape_xyz": list(cfg.grid_shape),
            "axis_order": ["component", "z", "y", "x"],
        }
        if any(root.attrs.get(k) != v for k, v in expected.items()):
            raise ValueError(f"{name}: unvalidated or mismatched frame metadata")
        array = root[name]
        if array.shape != (3, *cfg.full_shape_zyx):
            raise ValueError(f"{name}: unexpected shape {array.shape}")
        fields[name] = array
    return fields
