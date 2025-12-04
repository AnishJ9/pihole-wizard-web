"""
API routes for configuration generation.
"""

import io
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models import WizardState, ConfigPreviewResponse
from backend.core.config_generator import ConfigGenerator

router = APIRouter()
generator = ConfigGenerator()

# Output directory for generated configs
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


@router.post("/preview", response_model=ConfigPreviewResponse)
async def preview_config(state: WizardState):
    """Generate a preview of all configuration files without saving."""
    config = state.model_dump()
    files = generator.preview_all(config)
    commands = generator.get_commands_to_run(config)

    return ConfigPreviewResponse(
        files=files,
        commands_to_run=commands,
    )


@router.post("/generate")
async def generate_config(state: WizardState):
    """Generate and save configuration files to disk."""
    config = state.model_dump()

    try:
        created_files = generator.save_all(config, OUTPUT_DIR)
        return {
            "success": True,
            "output_dir": str(OUTPUT_DIR),
            "files": created_files,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download")
async def download_config(state: WizardState):
    """Generate configs and return as a downloadable ZIP file."""
    config = state.model_dump()
    files = generator.preview_all(config)

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            zf.writestr(f"pihole-config/{file.filename}", file.content)

        # Also include wizard config
        import json
        zf.writestr(
            "pihole-config/wizard-config.json",
            json.dumps(config, indent=2)
        )

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=pihole-config.zip"}
    )


@router.get("/files")
async def list_generated_files():
    """List files in the output directory."""
    if not OUTPUT_DIR.exists():
        return {"files": []}

    files = []
    for path in OUTPUT_DIR.rglob("*"):
        if path.is_file():
            files.append({
                "path": str(path.relative_to(OUTPUT_DIR)),
                "size": path.stat().st_size,
            })

    return {"files": files}
