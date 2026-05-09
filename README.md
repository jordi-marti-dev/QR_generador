# QR Code Batch Generator

A lightweight Python script that generates PNG QR codes from a JSON configuration file — no third-party services, no expiry links, no tracking.

> **Why not use a free QR website?**  
> Free online generators redirect through their own servers. If the service shuts down or changes its URL-shortening scheme, all your QR codes break. This script encodes the destination URL directly into the image, so it works forever without any external dependency.

---

## Features

- **GUI (PySide6)** — desktop window with form, colour picker, URL table, file dialogs, and live log panel
- Batch generation from a single JSON config
- Fully customisable: size, border, fill/background colour, error-correction level
- Load and save JSON config directly from the GUI
- Safe filename sanitisation (handles spaces and special characters)
- Structured logging with timestamps — written both to screen and to a `.log` file
- CLI interface with `--output-dir`, `--log-dir`, and `--verbose` flags
- Non-zero exit code on failure (compatible with CI/CD pipelines and shell scripts)
- Input validation with clear error messages before any file is written

---

## Requirements

- Python 3.8+
- `qrcode[pil]` — core QR generation
- `PySide6` — only needed for the GUI

```bash
pip install "qrcode[pil]" PySide6
```

---

## Installation

```bash
git clone https://github.com/<your-username>/qr-generator.git
cd qr-generator
pip install "qrcode[pil]"
```

No virtual environment is strictly required, but it is recommended:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install "qrcode[pil]"
```

---

## Usage

### Graphical interface (GUI)

```bash
python QR_GENERADOR_GUI.py
```

The GUI lets you:
- Fill in all QR parameters visually (no JSON editing required)
- Pick colours with a native colour-picker dialog
- Add / remove URLs from an editable table
- Browse for the output folder
- Load an existing `QR_CONFIG.json` or save the current form to a new one
- See a live log panel at the bottom — also saved to `logs/qr_YYYYMMDD_HHMMSS.log`

### Command-line interface (CLI)

```
python QR_GENERADOR.py [CONFIG] [-o OUTPUT_DIR] [-l LOG_DIR] [-v]
```

| Argument | Default | Description |
|---|---|---|
| `CONFIG` | `QR_CONFIG.json` | Path to the JSON configuration file |
| `-o`, `--output-dir` | `.` (current directory) | Directory where PNG files are saved |
| `-l`, `--log-dir` | `logs/` | Directory where `.log` files are saved |
| `-v`, `--verbose` | off | Enable debug-level logging |

### Examples

```bash
# Use the default config, save to current directory
python QR_GENERADOR.py

# Use a custom config and a custom output folder
python QR_GENERADOR.py my_config.json -o ./output

# Verbose mode (useful for debugging)
python QR_GENERADOR.py -v

# Full example
python QR_GENERADOR.py QR_CONFIG.json -o ./qrcodes -l ./logs -v
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All QR codes generated successfully |
| `1` | Config file not found, invalid JSON, or validation error |
| `>0` | One or more QR codes failed to generate |

---

## Configuration file

The config file is a JSON document with the following structure:

```json
{
    "version": 1,
    "size": 10,
    "border": 4,
    "fill_col": "black",
    "back_col": "white",
    "error_correction": "H",
    "urls": [
        ["Google",  "https://www.google.com"],
        ["GitHub",  "https://www.github.com"],
        ["My Site", "https://example.com/page?ref=qr"]
    ]
}
```

### Field reference

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | integer | Yes | QR version (1–40). Use `1` and let `fit=True` auto-adjust |
| `size` | integer | Yes | Pixel size of each QR module (box). Typical range: 5–20 |
| `border` | integer | Yes | Quiet-zone width in modules. Minimum recommended: 4 |
| `fill_col` | string | Yes | Foreground colour (module colour). Named colour or hex (`"#1a1a1a"`) |
| `back_col` | string | Yes | Background colour. Named colour or hex |
| `error_correction` | string | No | `L` (7%), `M` (15%), `Q` (25%), `H` (30%). Default: `H` |
| `urls` | array | Yes | List of `[name, url]` pairs. `name` becomes the filename |

**Generated filenames** follow the pattern `qrcode_<name>.png`, where any character that is not alphanumeric, a hyphen, or a period is replaced with `_`.

---

## Output example

```
2026-05-09 10:32:01 [INFO] Config loaded: 3 URL(s) to process.
2026-05-09 10:32:01 [INFO] OK  Google                         -> qrcode_Google.png
2026-05-09 10:32:01 [INFO] OK  GitHub                         -> qrcode_GitHub.png
2026-05-09 10:32:01 [INFO] OK  My Site                        -> qrcode_My_Site.png
2026-05-09 10:32:01 [INFO] Finished: 3/3 generated, 0 error(s).
```

---

## Running as a service / automation

Because the script returns meaningful exit codes and writes structured logs to stdout, it integrates cleanly into:

**Cron job (Linux/macOS)**
```bash
0 8 * * 1  /path/to/.venv/bin/python /path/to/QR_GENERADOR.py \
           /path/to/QR_CONFIG.json -o /var/www/html/qrcodes >> /var/log/qr.log 2>&1
```

**Windows Task Scheduler**
```
Program: C:\path\to\.venv\Scripts\python.exe
Arguments: C:\path\to\QR_GENERADOR.py QR_CONFIG.json -o C:\output
```

**GitHub Actions**
```yaml
- name: Generate QR codes
  run: |
    pip install "qrcode[pil]"
    python QR_GENERADOR.py QR_CONFIG.json -o ./qrcodes
  # Step fails automatically if exit code != 0
```

**Shell script with error check**
```bash
python QR_GENERADOR.py && echo "Done" || { echo "Generation failed"; exit 1; }
```

---

## Code structure

The project is split into two files with clear responsibilities:

### `QR_GENERADOR.py` — core logic (no GUI)

| Function | Purpose |
|---|---|
| `main()` | Entry point: parses CLI arguments, loads config, calls `generate()` |
| `_load_config(path)` | Reads and parses the JSON config file; exits with code 1 on error |
| `_validate_config(config)` | Checks all required fields, types and value ranges before generation |
| `generate(config, output_dir)` | Iterates over URLs, builds each QR image and saves it as PNG |
| `_safe_filename(name)` | Sanitises a string so it can be used safely as a file name |
| `_setup_logging(verbose, log_dir)` | Creates a console handler and a timestamped `.log` file handler |
| `_build_parser()` | Defines the CLI arguments (`config`, `-o`, `-l`, `-v`) |

### `QR_GENERADOR_GUI.py` — graphical interface (PySide6)

**Helper classes**

| Class | Purpose |
|---|---|
| `_QTextEditHandler` | `logging.Handler` subclass that writes coloured log messages to a `QTextEdit` |
| `ColorButton` | `QPushButton` that shows the current colour and opens a native colour picker |
| `CollapsibleBox` | `QWidget` with a clickable header that hides/shows its content area |

**`MainWindow` methods**

| Method | Purpose |
|---|---|
| `__init__` | Builds the window: menu bar, vertical layout and all panels |
| `_build_menu` | Creates the `Ajuda → Quant a...` menu entry (shortcut: F1) |
| `_show_about` | Shows the About dialog with version, description and author links |
| `_build_config_group` | Collapsible panel with all QR visual parameters |
| `_build_url_group` | URL list panel with Manual / JSON mode selector and dynamic buttons |
| `_build_output_group` | Collapsible panel to choose the PNG output directory |
| `_build_action_row` | Bottom row with the main "Generate" button |
| `_build_preview_group` | Horizontally scrollable panel for generated QR thumbnails |
| `_build_log_group` | Execution log panel with dark background |
| `_init_logging` | Connects `logging` to both the log file and the GUI panel |
| `_add_url_row` | Appends a new editable row to the URL table |
| `_remove_url_row` | Removes the selected row (or the last one if none selected) |
| `_on_url_mode_changed` | Switches button bar and table edit mode between Manual and JSON |
| `_browse_output` | Opens a native folder picker and updates the output path field |
| `_build_config` | Reads the form and returns a config dictionary |
| `_populate_form` | Fills all form fields from a config dictionary |
| `_load_json` | Opens a JSON file and loads its config into the form |
| `_save_json` | Saves the current form config to a JSON file |
| `_on_generate` | Validates, generates QR codes and refreshes the preview panel |
| `_populate_preview` | Clears old thumbnails and creates one per generated PNG |
| `_make_thumbnail` | Creates a clickable thumbnail button from a PNG file |
| `_show_full_qr` | Opens a modal dialog showing the QR at full size (450×450 px) |

---

## Author

**Jordi Martí**  
🌐 [jordimarti.dev](https://jordimarti.dev)  
📦 [github.com/jordi-marti-dev/QR_generador](https://github.com/jordi-marti-dev/QR_generador)  
✉ jordi.marti.dev@gmail.com

---

## Roadmap

- [x] GUI desktop (PySide6) with form, colour picker, URL table and live log
- [x] Documented functions for educational use
- [ ] Optional logo/watermark overlay on the QR image
- [ ] SVG output support
- [ ] REST API wrapper (Flask / FastAPI) for on-demand generation
- [ ] Docker image for containerised deployments
- [ ] Schema validation via `jsonschema`

---

## License

MIT — free to use, modify, and distribute.
