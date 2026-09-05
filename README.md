# MONAD

MONAD is a small collection of local tools and experiments, with a shell
launcher for the Flask applications in `projects/`.

## Included applications

| Application | Purpose | Port |
| --- | --- | ---: |
| `diarix` | Media upload, cutting, transcription, and optional speaker diarization | 5030 |
| `bfc` | Media editing and document utilities, depending on the current app implementation | 5034 |
| `vd` | Video download and media processing from uploads or URLs | 5005 |

The root `index.html` provides links to the local applications. The
application-specific documentation and specifications live in each project
directory.

## Requirements

- Linux or macOS
- Bash and, for `lau.sh`, Zsh-compatible shell utilities
- Python 3.12 or 3.13
- `pip`
- `ffmpeg` and `ffprobe` for the media applications
- `lsof` and `ping` for the launcher scripts

Some applications also require large or platform-specific Python packages
such as Whisper, `pyannote.audio`, PyMuPDF, and EbookLib. These are installed
from the requirements file for each application.

## Quick start

From the repository root, create an environment and launch all applications:

```bash
./lau.sh
```

`lau.sh` creates or reuses a root `.venv`, installs the dependencies while
running `test.sh`, stops processes already using the application ports, and
launches each directory under `projects/`. It waits for network connectivity
before starting. To recreate the environment from scratch:

```bash
./lau.sh --cold
```

The launcher expects the application dependencies to be available in:

```text
projects/diarix/requirements.txt
projects/bfc/requirements.txt
projects/vd/requirements.txt
```

Open `index.html` in a browser after the applications start, or visit:

- <http://127.0.0.1:5030>
- <http://127.0.0.1:5034>
- <http://127.0.0.1:5005>

To start one application manually:

```bash
cd projects/diarix
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Use the corresponding directory and requirements file for `bfc` or `vd`.

## Environment variables

The launcher exports:

- `DEMO` — enabled automatically on Linux; used to select Linux-specific
  dependency behavior.
- `VER` — Python version used by the launcher (`3.13` on Linux, `3.12`
  otherwise).

The applications may use provider credentials when their optional AI features
are enabled. See the application source and README files for the exact
environment variable names and supported providers.

## Utility scripts

- `pacbuild.sh` compiles `pac.c`, asks for confirmation, and installs the
  resulting timestamp-prefixing utility as `/usr/local/bin/pac`.
- `pac.c` copies standard input to standard output and prefixes each new line
  with a nanosecond timestamp.
- `instal` copies the repository's `zsh_aliases` file to `~/.zsh_aliases` and
  adds a source line to `~/.zshrc` when needed.
- `update.sh` removes `$HOME/MONAD`, clones
  `https://github.com/CorneliuBoboc/MONAD.git`, and enters the fresh clone.
- `test.sh <application>` installs that application's requirements and checks
  that its Flask process starts.

Review scripts before running them: `lau.sh` terminates processes using the
configured ports, `--cold` removes virtual environments and the local pip
cache, and `update.sh` removes an existing `$HOME/MONAD` directory.

## Project layout

```text
.
├── index.html          # Links to the local web applications
├── lau.sh              # Main launcher
├── test.sh             # Per-application dependency/startup check
├── pac.c               # Timestamp-prefixing stdin utility
├── pacbuild.sh         # Build/install script for pac
└── projects/
    ├── diarix/
    ├── bfc/
    └── vd/
```

## Development notes

The applications are personal/local tools and are not configured as a
production deployment. Do not expose them to an untrusted network without
adding authentication, request limits, and an appropriate production server.
