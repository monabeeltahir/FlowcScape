# Attune-Style Flow Cytometry Dashboard

This project is a structured PySide6 desktop application for loading flow cytometry data and building an Attune-inspired analysis workspace.

## Current capabilities

- Load one or more `.fcs` files as a single experiment with multiple samples
- Best-effort `.atx` support when the file is a container with embedded FCS files
- Attune-style 3-pane layout:
  - left: plot controls for the selected plot
  - center: 3x3 plot workspace
  - right: experiment and sample browser
- Layout presets for `4`, `6`, or `9` visible plot panels
- Right-click each plot cell to insert:
  - Histogram Plot
  - Dot Plot
  - Density Plot
- Per-plot customization:
  - x/y parameter selection
  - linear or log scale per axis
  - manual or automatic ranges
  - bin count
  - title
  - axis label font size
  - export DPI
- Export selected plots as high-resolution images

## Notes about `.atx`

`Attune .atx` files are not openly documented in a stable way. This app currently:

- tries to read `.atx` as a container file
- loads embedded `.fcs` files when available
- falls back to using multiple `.fcs` files as one experiment if `.atx` cannot be parsed

That keeps the architecture ready for a richer `.atx` parser later without changing the GUI design.

## Run

```powershell
cd "c:\Users\mt1102\Documents\Python Scripts\FlowScape"
python main.py
```

## Project structure

```text
FlowScape/
  main.py
  app/
    main_window.py
    models.py
    state.py
    services/
    plotting/
    widgets/
```

## Extensibility

The code is split so you can add features like gates, overlays, statistics panels, compensation tools, or workspace persistence without rewriting the current app shell.
