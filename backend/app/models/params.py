"""
Parameter schemas for specialist tools.

These are the only knobs the controller may set on a tool. Unknown or
out-of-range values are rejected, which keeps every run reproducible from
its execution trace.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolParams(BaseModel):
    """Base for tool parameters. Unknown parameters are rejected."""

    model_config = ConfigDict(extra="forbid")


class NoParams(ToolParams):
    pass


class VQAParams(ToolParams):
    max_new_tokens: int = Field(default=30, ge=1, le=100)


class ChangeParams(ToolParams):
    sensitivity: float = Field(
        default=3.0,
        ge=1.0,
        le=10.0,
        description="How many robust standard deviations above the scene's "
        "typical difference a pixel must be to count as changed. "
        "Lower finds more (and noisier) change.",
    )
    min_region_px: int = Field(
        default=25,
        ge=1,
        le=100_000,
        description="Changed regions smaller than this are discarded.",
    )
    max_regions: int = Field(default=20, ge=1, le=200)
    registration_tolerance_px: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Misalignment between the two images, in pixels, that "
        "should not be reported as change.",
    )


class GroundingParams(ToolParams):
    score_threshold: float = Field(default=0.10, ge=0.01, le=0.90)
    tile_size: int = Field(default=768, ge=256, le=2048)
    max_tiles: int = Field(default=16, ge=1, le=64)
    max_detections: int = Field(default=50, ge=1, le=500)


class SARParams(ToolParams):
    speckle_window: int = Field(
        default=5,
        ge=3,
        le=11,
        description="Side of the square speckle-filter window, in pixels (odd).",
    )
    min_contrast_db: float = Field(
        default=5.0,
        ge=2.0,
        le=20.0,
        description="How much darker than the rest of the scene a surface "
        "must be to be reported as low-backscatter (water-like).",
    )
    min_region_px: int = Field(default=50, ge=1, le=100_000)
    max_regions: int = Field(default=20, ge=1, le=200)
    cfar_k: float = Field(
        default=5.0,
        ge=3.0,
        le=10.0,
        description="Standard deviations above the local background a "
        "bright target must reach.",
    )
    min_target_px: int = Field(default=3, ge=1, le=1_000)
    max_targets: int = Field(default=50, ge=1, le=500)

    @field_validator("speckle_window")
    @classmethod
    def _window_must_be_odd(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("speckle_window must be odd")

        return value
