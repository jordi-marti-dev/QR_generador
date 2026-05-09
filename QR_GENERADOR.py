#!/usr/bin/env python3
"""
QR code batch generator from a JSON configuration file.

Generates PNG QR codes for each URL defined in the config.
Designed to run as a standalone script or inside an automated pipeline.

Usage:
    python QR_GENERADOR.py [config] [-o OUTPUT_DIR] [-v]

Example:
    python QR_GENERADOR.py QR_CONFIG.json -o ./output -v
"""

import argparse
import datetime
import json
import logging
import re
import sys
from pathlib import Path

import qrcode  # pip install "qrcode[pil]"

_ERROR_CORRECTIONS = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}

_URL_PATTERN = re.compile(r"^https?://\S+$", re.IGNORECASE)
_UNSAFE_CHARS = re.compile(r"[^\w\-.]")
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

log = logging.getLogger(__name__)


def _setup_logging(verbose: bool, log_dir: Path) -> Path:
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"qr_{timestamp}.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)

    return log_path


def _load_config(config_path: Path) -> dict:
    try:
        with config_path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log.error("Config file not found: %s", config_path)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        log.error("Invalid JSON in config file: %s", exc)
        sys.exit(1)


def _validate_config(config: dict) -> None:
    required = {"version", "size", "border", "fill_col", "back_col", "urls"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(sorted(missing))}")

    version = config["version"]
    if not isinstance(version, int) or not (1 <= version <= 40):
        raise ValueError(f"'version' must be an integer between 1 and 40, got {version!r}")

    if not isinstance(config["size"], int) or config["size"] < 1:
        raise ValueError(f"'size' must be a positive integer, got {config['size']!r}")

    if not isinstance(config["border"], int) or config["border"] < 0:
        raise ValueError(f"'border' must be a non-negative integer, got {config['border']!r}")

    if not isinstance(config["urls"], list) or len(config["urls"]) == 0:
        raise ValueError("'urls' must be a non-empty list")

    for i, entry in enumerate(config["urls"]):
        if not (isinstance(entry, (list, tuple)) and len(entry) == 2):
            raise ValueError(f"urls[{i}] must be a [name, url] pair, got {entry!r}")
        name, url = entry
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"urls[{i}]: name must be a non-empty string")
        if not isinstance(url, str) or not _URL_PATTERN.match(url):
            raise ValueError(f"urls[{i}] ({name!r}): invalid URL {url!r}")

    ec = config.get("error_correction", "H")
    if ec.upper() not in _ERROR_CORRECTIONS:
        raise ValueError(
            f"'error_correction' must be one of {list(_ERROR_CORRECTIONS)}, got {ec!r}"
        )


def _safe_filename(name: str, max_len: int = 80) -> str:
    sanitized = _UNSAFE_CHARS.sub("_", name.strip())
    return sanitized[:max_len] or "qr"


def generate(config: dict, output_dir: Path) -> int:
    """Generate QR codes for all URLs in config. Returns number of errors."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ec_key = config.get("error_correction", "H").upper()
    error_correction = _ERROR_CORRECTIONS[ec_key]

    errors = 0
    for name, url in config["urls"]:
        try:
            qr = qrcode.QRCode(
                version=config["version"],
                error_correction=error_correction,
                box_size=config["size"],
                border=config["border"],
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(
                fill_color=config["fill_col"],
                back_color=config["back_col"],
            )
            out_path = output_dir / f"qrcode_{_safe_filename(name)}.png"
            img.save(out_path)
            log.info("OK  %-30s -> %s", name, out_path.name)
        except Exception as exc:
            log.error("FAIL %-30s -> %s", name, exc)
            errors += 1

    total = len(config["urls"])
    log.info("Finished: %d/%d generated, %d error(s).", total - errors, total, errors)
    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="QR_CONFIG.json",
        metavar="CONFIG",
        help="Path to the JSON config file (default: QR_CONFIG.json)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=".",
        metavar="DIR",
        help="Output directory for PNG files (default: current directory)",
    )
    parser.add_argument(
        "-l", "--log-dir",
        default="logs",
        metavar="DIR",
        help="Directory where .log files are saved (default: logs/)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    log_path = _setup_logging(args.verbose, Path(args.log_dir))
    log.info("Log file: %s", log_path)

    config = _load_config(Path(args.config))

    try:
        _validate_config(config)
    except ValueError as exc:
        log.error("Config validation error: %s", exc)
        return 1

    log.info("Config loaded: %d URL(s) to process.", len(config["urls"]))
    return generate(config, Path(args.output_dir))


if __name__ == "__main__":
    sys.exit(main())
