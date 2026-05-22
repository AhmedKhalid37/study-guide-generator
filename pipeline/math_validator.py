from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_VALIDATOR = BASE_DIR / "scripts" / "validate_math.js"


@dataclass(frozen=True)
class MathError:
    expr: str
    display_mode: bool
    message: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[MathError]
    display_blocks: int
    inline_formulas: int
    raw_stdout: str = ""
    raw_stderr: str = ""

    def to_json_dict(self) -> dict:
        return {
            "ok": self.ok,
            "displayBlocks": self.display_blocks,
            "inlineFormulas": self.inline_formulas,
            "errors": [asdict(error) for error in self.errors],
            "stdout": self.raw_stdout,
            "stderr": self.raw_stderr,
        }


def validate(
    md_path: Path,
    *,
    validator: Path = DEFAULT_VALIDATOR,
    output_json: Path | None = None,
) -> ValidationResult:
    if not shutil.which("node"):
        result = ValidationResult(
            ok=True,
            errors=[],
            display_blocks=0,
            inline_formulas=0,
            raw_stderr="node is not installed; skipped KaTeX validation.",
        )
        _write_json(output_json, result)
        return result

    if not validator.exists():
        result = ValidationResult(
            ok=True,
            errors=[],
            display_blocks=0,
            inline_formulas=0,
            raw_stderr=f"{validator} does not exist; skipped KaTeX validation.",
        )
        _write_json(output_json, result)
        return result

    proc = subprocess.run(
        ["node", str(validator), str(md_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    result = _parse_result(proc.returncode, proc.stdout, proc.stderr)
    _write_json(output_json, result)
    return result


def _parse_result(returncode: int, stdout: str, stderr: str) -> ValidationResult:
    counts_match = re.search(
        r"Display blocks:\s*(\d+),\s*inline formulas:\s*(\d+)",
        stdout,
    )
    display_blocks = int(counts_match.group(1)) if counts_match else 0
    inline_formulas = int(counts_match.group(2)) if counts_match else 0

    errors = _parse_errors(stderr)
    return ValidationResult(
        ok=returncode == 0 and not errors,
        errors=errors,
        display_blocks=display_blocks,
        inline_formulas=inline_formulas,
        raw_stdout=stdout,
        raw_stderr=stderr,
    )


def _parse_errors(stderr: str) -> list[MathError]:
    errors: list[MathError] = []
    current_display: bool | None = None
    current_expr: str | None = None

    for line in stderr.splitlines():
        header = re.match(r"#\d+\s+(display|inline)", line.strip())
        if header:
            current_display = header.group(1) == "display"
            current_expr = None
            continue

        if current_display is not None and current_expr is None and line.strip():
            current_expr = line
            continue

        if current_display is not None and current_expr is not None and line.strip():
            errors.append(
                MathError(
                    expr=current_expr,
                    display_mode=current_display,
                    message=line,
                )
            )
            current_display = None
            current_expr = None

    return errors


def _write_json(path: Path | None, result: ValidationResult) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_json_dict(), indent=2) + "\n", encoding="utf-8")
