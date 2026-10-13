"""Tests for the AI engine: device detection, runtime utilities, exporters,
output validation, and end-to-end generation via the engine base class.
"""

from __future__ import annotations

import asyncio

from app.ai.exporters.gltf import glb_to_embedded_gltf, validate_glb_bytes
from app.ai.exporters.preview import render_preview
from app.ai.factory import create_ai_model
from app.ai.geometry.stats import compute_mesh_stats
from app.ai.inference.device import (
    get_device_info,
    resolve_device,
    vram_snapshot,
)
from app.ai.inference.runtime import (
    BatchProcessor,
    ErrorClassifier,
    compute_backoff,
    retry_async,
)
from app.ai.inference.validator import OutputValidator
from app.ai.models.base_model import ImageTo3DModel
from app.ai.types import (
    GenerationResult,
    GenerationSettings,
    QualityReport,
    TransientError,
)
from tests.conftest import make_test_image

# -- Device detection / VRAM ------------------------------------------------


def test_resolve_device_cpu_preference():
    assert resolve_device("cpu") == "cpu"


def test_device_info_is_always_available():
    info = get_device_info("cpu")
    assert info.type in ("cpu", "cuda")
    assert isinstance(info.to_dict(), dict)
    assert info.to_dict()["type"] == info.type


def test_vram_snapshot_shape():
    snap = vram_snapshot()
    assert set(snap) == {"device", "total_mb", "used_mb", "free_mb", "allocated_mb", "reserved_mb"}


# -- Error classification / retries -----------------------------------------


def test_error_classifier_marks_transient():
    assert ErrorClassifier.is_transient(TimeoutError("timed out"))
    assert ErrorClassifier.is_transient(TransientError("boom"))
    assert ErrorClassifier.is_transient(RuntimeError("cuda out of memory"))
    assert not ErrorClassifier.is_transient(ValueError("invalid input"))


def test_compute_backoff_exponential():
    assert compute_backoff(1, base_delay=2.0) == 2.0
    assert compute_backoff(2, base_delay=2.0) == 4.0
    assert compute_backoff(10, base_delay=2.0, max_delay=30.0) == 30.0


def test_retry_async_succeeds_after_transient_failures():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("transient hiccup")
        return "ok"

    result = asyncio.run(retry_async(flaky, retries=5, base_delay=0.01))
    assert result == "ok"
    assert calls["n"] == 3


def test_retry_async_does_not_retry_fatal():
    async def fatal():
        raise ValueError("bad")

    try:
        asyncio.run(retry_async(fatal, retries=3, base_delay=0.01))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


# -- Batch processing -------------------------------------------------------


def test_batch_processor_bounded_concurrency():
    active = {"now": 0, "peak": 0}

    async def worker(index, item):
        active["now"] += 1
        active["peak"] = max(active["peak"], active["now"])
        await asyncio.sleep(0.02)
        active["now"] -= 1
        return item * 2

    results = asyncio.run(BatchProcessor(concurrency=2).run([1, 2, 3, 4], worker))
    assert results == [2, 4, 6, 8]
    assert active["peak"] <= 2


# -- Exporters --------------------------------------------------------------


def test_glb_validation_and_conversion():
    import trimesh

    glb = trimesh.creation.box(extents=[1, 1, 1]).export(file_type="glb")
    assert validate_glb_bytes(glb) is None
    gltf = glb_to_embedded_gltf(glb)
    assert b"data:application/octet-stream;base64," in gltf

    assert validate_glb_bytes(b"") is not None
    assert validate_glb_bytes(b"garbage-not-glb") is not None


def test_preview_render_returns_png():
    import trimesh

    mesh = trimesh.creation.box(extents=[1, 1, 1])
    preview = render_preview(mesh)
    assert preview is not None
    assert preview[:8] == b"\x89PNG\r\n\x1a\n"


# -- Mesh statistics --------------------------------------------------------


def test_compute_mesh_stats():
    import trimesh

    mesh = trimesh.creation.box(extents=[2, 2, 2])
    stats = compute_mesh_stats(mesh)
    assert stats["vertices"] == 8
    assert stats["faces"] == 12
    assert stats["watertight"] is True
    assert stats["extents"] is not None


# -- Output validation ------------------------------------------------------


def test_output_validator_passes_valid_textured_model():
    import numpy as np
    import trimesh
    from PIL import Image
    from trimesh.visual.material import SimpleMaterial
    from trimesh.visual.texture import TextureVisuals

    mesh = trimesh.creation.box(extents=[1, 1, 1])
    tex = Image.new("RGB", (8, 8), (90, 120, 200))
    uv = np.array(
        [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0], [1, 0], [1, 1], [0, 1]],
        dtype=float,
    )
    mesh.visual = TextureVisuals(uv=uv, image=tex, material=SimpleMaterial(image=tex))
    glb = mesh.export(file_type="glb")
    result = GenerationResult(glb_bytes=glb, stats=compute_mesh_stats(mesh))
    report = OutputValidator.validate(result, settings=GenerationSettings(validation="warn"))
    assert isinstance(report, QualityReport)
    assert report.passed is True


def test_output_validator_flags_missing_texture():
    import trimesh

    glb = trimesh.creation.box(extents=[1, 1, 1]).export(file_type="glb")
    result = GenerationResult(glb_bytes=glb, stats={})
    report = OutputValidator.validate(result, settings=GenerationSettings(validation="warn"))
    by_name = {c.name: c for c in report.checks}
    assert by_name["texture_present"].passed is False


def test_output_validator_rejects_garbage_glb():
    result = GenerationResult(glb_bytes=b"not-a-glb", stats={})
    report = OutputValidator.validate(result, settings=GenerationSettings(validation="warn"))
    by_name = {c.name: c for c in report.checks}
    assert by_name["glb_valid"].passed is False
    assert report.passed is False


def test_output_validator_detects_empty_mesh():
    import trimesh

    glb = trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0]], faces=[]).export(file_type="glb")
    result = GenerationResult(glb_bytes=glb, stats={})
    report = OutputValidator.validate(result, settings=GenerationSettings(validation="warn"))
    by_name = {c.name: c for c in report.checks}
    assert by_name["mesh_not_empty"].passed is False


# -- Engine end-to-end ------------------------------------------------------


def _test_image(tmp_path) -> str:
    p = tmp_path / "in.png"
    p.write_bytes(make_test_image("PNG", width=64, height=48))
    return str(p)


def test_mock_generate_produces_all_outputs(tmp_path):
    model = create_ai_model("mock")
    assert isinstance(model, ImageTo3DModel)
    settings = GenerationSettings(resolution=48, formats=["glb", "gltf", "obj", "preview"])
    result = asyncio.run(model.generate(_test_image(tmp_path), tmp_path / "out", settings))

    assert result.glb_bytes[:4] == b"glTF"
    assert result.gltf_bytes is not None
    assert result.obj_bytes is not None and result.obj_bytes.startswith(b"#")
    assert result.preview_bytes is not None and result.preview_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert result.stats["vertices"] > 0
    assert result.stats["faces"] > 0
    assert result.timings, "stage timings should be recorded"
    assert result.device["type"] in ("cpu", "cuda")
    assert result.validation is not None and result.validation["passed"] is True


def test_mock_generate_skips_aux_when_not_requested(tmp_path):
    model = create_ai_model("mock")
    settings = GenerationSettings(resolution=48, formats=["glb"])
    result = asyncio.run(model.generate(_test_image(tmp_path), tmp_path / "out2", settings))
    assert result.preview_bytes is None
    assert result.obj_bytes is None


def test_mock_generate_batch(tmp_path):
    model = create_ai_model("mock")
    settings = GenerationSettings(resolution=48, formats=["glb"])
    images = [_test_image(tmp_path), _test_image(tmp_path)]
    results = asyncio.run(model.generate_batch(images, tmp_path / "batch", settings, concurrency=2))
    assert len(results) == 2
    for r in results:
        assert r.glb_bytes[:4] == b"glTF"


def test_strict_validation_raises_on_broken_result(tmp_path):
    class BrokenModel(ImageTo3DModel):
        name = "broken"

        def _generate_sync(self, image_path, output_dir, settings, progress):
            import trimesh

            glb = trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0]], faces=[]).export(file_type="glb")
            return GenerationResult(glb_bytes=glb, stats={})

    model = BrokenModel()
    settings = GenerationSettings(resolution=48, formats=["glb"], validation="strict")
    try:
        asyncio.run(model.generate(_test_image(tmp_path), tmp_path / "out3", settings))
    except Exception as exc:
        assert "validation" in str(exc).lower()
    else:
        raise AssertionError("expected validation failure")


def test_broken_model_skips_validation_when_off(tmp_path):
    class BrokenModel(ImageTo3DModel):
        name = "broken2"

        def _generate_sync(self, image_path, output_dir, settings, progress):
            import trimesh

            glb = trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0]], faces=[]).export(file_type="glb")
            return GenerationResult(glb_bytes=glb, stats={})

    model = BrokenModel()
    settings = GenerationSettings(resolution=48, formats=["glb"], validation="off")
    result = asyncio.run(model.generate(_test_image(tmp_path), tmp_path / "out4", settings))
    assert result.glb_bytes[:4] == b"glTF"
    assert result.validation is None


def test_transient_error_is_retried(tmp_path):
    calls = {"n": 0}

    class FlakyModel(ImageTo3DModel):
        name = "flaky"

        def _generate_sync(self, image_path, output_dir, settings, progress):
            calls["n"] += 1
            if calls["n"] < 2:
                raise TransientError("transient failure during inference")
            import trimesh

            glb = trimesh.creation.box(extents=[1, 1, 1]).export(file_type="glb")
            return GenerationResult(glb_bytes=glb, stats=compute_mesh_stats(trimesh.creation.box()))

    model = FlakyModel()
    settings = GenerationSettings(resolution=48, formats=["glb"], retries=3, validation="off")
    result = asyncio.run(model.generate(_test_image(tmp_path), tmp_path / "out5", settings))
    assert calls["n"] == 2
    assert result.extra["retries"] == 1
