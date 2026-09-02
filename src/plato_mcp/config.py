"""PLATO credential/config loading.

Local dev: reads PNU_STUDENTS_ID / PNU_STUDENTS_PASSWORD from .env / the
process environment. On Smithery this will be replaced by per-user config
injection -- exactly how is still open (issue #21). This module is the one
place that needs to change once that's confirmed; everything else consumes
`PlatoConfig`, not the raw env vars.
"""

import os

from dotenv import dotenv_values
from pydantic import BaseModel


class PlatoConfig(BaseModel):
    pnu_id: str
    pnu_password: str
    request_timeout_seconds: int = 15
    max_download_mb: int = 20


def load_config() -> PlatoConfig:
    env = {**dotenv_values(), **os.environ}
    pnu_id = env.get("PNU_STUDENTS_ID")
    pnu_password = env.get("PNU_STUDENTS_PASSWORD")
    if not pnu_id or not pnu_password:
        raise RuntimeError(
            "PNU_STUDENTS_ID / PNU_STUDENTS_PASSWORD not set (.env or environment)"
        )
    return PlatoConfig(pnu_id=pnu_id, pnu_password=pnu_password)
