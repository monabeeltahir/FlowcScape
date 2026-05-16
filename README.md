# FlowScape

FlowScape is a Python desktop application for flow cytometry data review and analysis. It is designed as an Attune-inspired workspace for loading `.fcs` or supported `.atx` experiment containers, creating plots, applying gates, and building histogram overlays.

## What the software does

- Load one or more `.fcs` files as a single experiment
- Load supported Attune `.atx` files and extract:
  - experiment name
  - sample names
  - group structure
  - embedded FCS event data
- Display experiments and samples in a right-side tree
- Build plots in a center grid workspace
- Edit plot settings from the left panel
- Create gates on histogram and 2D plots
- Reuse gates as data sources for downstream plots
- Send histogram plots to a separate overlay workspace
- Export plots at high DPI

## Current plot types

- `Histogram Plot`
- `Dot Plot`
- `Density Plot`

## Current gate types

- `Histogram Gate`
- `Rectangle Gate`
- `Oval Gate`
- `Polygon Gate`
- `Quadrant Gate`

## Installation

Create and activate a Python environment, then install dependencies:

```powershell
cd "c:\Users\mt1102\Documents\Python Scripts\FlowScape"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
cd "c:\Users\mt1102\Documents\Python Scripts\FlowScape"
python main.py
```

## Main window layout

FlowScape uses a 3-pane layout:

- Left panel: selected plot settings and styling controls
- Center panel: plot workspace grid
- Right panel: experiments and samples

Top toolbar modes:

- Home toolbar
  - `Open FCS Files`
  - `Open ATX File`
  - `4 Panels`
  - `6 Panels`
  - `9 Panels`
  - `Workspace`
  - `Overlay`
- Workspace toolbar
  - plot insertion buttons
  - gate tools
  - gate color
  - overlay send button
  - export / clear / delete gate actions

## Basic workflow

### 1. Load data

Use one of:

- `Open FCS Files`
- `Open ATX File`

Notes:

- When you load `.fcs` files, the application groups them into a single experiment.
- When you load a supported Attune `.atx`, FlowScape reads `experiment.xml` inside the archive to recover the experiment name, sample names, and group structure.

### 2. Select a sample

In the right panel:

- single-click a sample to make it the current sample
- double-click a sample to apply that sample to the visible workspace plots

### 3. Create a plot

There are two main ways:

- click `Workspace`, then use:
  - `Histogram Plot`
  - `Dot Plot`
  - `Density Plot`
- or right-click an empty plot cell and choose `Insert`

### 4. Adjust the grid

Use:

- `4 Panels`
- `6 Panels`
- `9 Panels`

or manually change:

- `Grid Rows`
- `Grid Columns`

The center area is scrollable, so plot tile size stays fixed when the grid grows.

### 5. Choose X and Y parameters

The axis selectors use a two-step dropdown model:

- first dropdown: base detector/channel
  - examples: `FSC`, `SSC`, `BL1`, `BL2`, `VL1`
- second dropdown: signal component
  - examples: `A`, `H`, `W`

Examples:

- `FSC` + `A` becomes `FSC-A`
- `SSC` + `H` becomes `SSC-H`
- `BL2` + `H` becomes `BL2-H`

Parameters such as `Time` that do not use `-A / -H / -W` remain selectable as a single base parameter.

### 6. Change plot appearance

In the left panel, you can edit:

- plot type
- X parameter
- Y parameter
- X scale: `Linear` or `Log`
- Y scale: `Linear` or `Log`
- automatic or manual axis ranges
- plot title
- histogram bin count
- histogram style: `Line` or `Bar`
- histogram color
- density gridsize
- density minimum count
- density colormap
- gate label mode
- font size
- export DPI

### 7. Create gates

Select a plot, then use one of:

- `Histogram Gate`
- `Rectangle Gate`
- `Oval Gate`
- `Polygon Gate`
- `Quadrant Gate`

Behavior:

- Histogram gates work on histogram plots
- Rectangle, oval, polygon, and quadrant gates work on dot and density plots

### 8. Edit or move gates

Once a gate is drawn:

- click the gate to select it
- drag the whole gate to move it
- drag the gate handles to reshape it
- press `Delete` or use `Delete Selected Gate` to remove it

You can also right-click a plot and use:

- `Edit Gate`
- `Statistics`
- `Export Plot`
- `Clear Plot`

### 9. Use a gate as the data source for another plot

Each plot can use:

- `All Events`
- or a previously created gate

This is controlled by the `Source` dropdown in the `Selected Plot` section.

Typical use:

1. create a gate on one plot
2. select another plot cell
3. insert a new plot
4. change `Source` from `All Events` to that gate

### 10. Send histogram plots to overlay

Overlay is histogram-only.

To use it:

1. create or select a histogram plot in the main workspace
2. click `Send Selected To Overlay`
   - or right-click the plot and choose `Send To Overlay`
3. choose:
   - an existing overlay plot
   - or `New Overlay Plot`

The overlay window keeps:

- source histogram color
- histogram style

Inside the overlay window you can:

- create histogram gates
- change series color
- change series transparency from `0` to `1`
- export the selected overlay plot
- clear an overlay plot
- delete the selected overlay gate

## Plot export

Use either:

- `Export Selected Plot` from the toolbar
- `Export Plot` from the plot right-click menu

Supported export targets:

- `.png`
- `.tiff`
- `.pdf`

Export quality is controlled by `Export DPI` in the left panel.

## Statistics

Plot right-click menus include `Statistics`.

For plots and gates, the application can report:

- count
- percentage
- mean of X
- median of X
- mean of Y
- median of Y

Overlay statistics are reported per overlaid histogram series.

## File format notes

### FCS

FCS loading is implemented directly in Python. The loader reads:

- FCS header
- text segment metadata
- parameter names
- event matrix

### ATX

`.atx` support is currently based on container-style Attune exports that contain:

- embedded `.fcs` files
- Attune XML metadata such as `experiment.xml`

FlowScape currently uses the XML metadata to recover:

- experiment display name
- sample display names
- sample grouping

If a future `.atx` file uses a different internal structure, additional parser work may be needed.

## Libraries used

### Runtime dependencies

- `PySide6`
  - desktop GUI
  - main window
  - dialogs
  - tree views
  - toolbars
  - custom widgets
- `matplotlib`
  - histogram, dot, density, and overlay rendering
  - gate overlays
  - figure export
- `numpy`
  - array operations
  - filtering
  - histogram bin generation
  - point subsampling
- `pandas`
  - event tables for cytometry data
  - parameter-column based filtering
  - statistics support
- `scipy`
  - currently included in requirements for numerical extensions
  - not heavily used in the current implementation yet

### Python standard library used in the project

- `zipfile`
  - read `.atx` container contents
- `xml.etree.ElementTree`
  - parse Attune XML metadata such as `experiment.xml`
- `pathlib`
  - file and path handling
- `dataclasses`
  - application data models
- `enum`
  - plot type and gate type definitions
- `uuid`
  - internal IDs

## Project structure

```text
FlowScape/
  main.py
  README.md
  requirements.txt
  app/
    __init__.py
    main_window.py
    models.py
    state.py
    theme.py
    plotting/
      __init__.py
      config.py
      renderer.py
    services/
      atx_loader.py
      experiment_loader.py
      fcs_loader.py
      gating.py
    widgets/
      experiment_tree.py
      gate_editor_dialog.py
      overlay_window.py
      plot_cell.py
      plot_config_panel.py
      plot_grid.py
      stepper_spinbox.py
```

## Known limitations

- `.atx` support depends on the internal export structure being compatible with the current parser
- compensation workflows are not implemented as full analysis tools yet
- workspace save/load is not implemented yet
- some advanced Attune-specific analysis behaviors are still approximated

## Development notes

The codebase is intentionally split into:

- `services` for file parsing and data logic
- `plotting` for figure generation
- `widgets` for reusable GUI components
- `models` and `state` for shared app data

That structure makes it easier to add future features such as:

- persistent workspaces
- additional statistics
- compensation editing
- more advanced overlays
- gate libraries
- batch processing
