# Orthogonal Measure — QGIS Plugin

**Version:** 0.1 · **Author:** Darko Nedic · **Contact:** office@geo-biz.com  
**License:** GNU GPL v2+  
**Minimum QGIS version:** 3.0

---

## Overview

**Orthogonal Measure** is a QGIS plugin that lets you define a **local orthogonal coordinate system** directly on the map canvas and then construct points by entering **X and Y offsets in metres**. It is designed for surveyors, civil engineers, and GIS professionals who need to quickly stake out or digitize points relative to a custom baseline — without leaving QGIS.

The plugin works correctly in **any CRS** (projected or geographic) because all offset calculations use ellipsoidal ground distances.

---

## How It Works

### Coordinate System Definition

1. **Point 1 — Origin (0, 0):** Click anywhere on the map to place the origin of your local system.
2. **Point 2 — Y-axis direction:** Click a second point. The direction from Point 1 to Point 2 defines the **positive Y-axis**.
3. **X-axis** is automatically computed as **perpendicular to the Y-axis, rotated 90° clockwise**.

Both axes are visualized on the map canvas:

| Axis | Colour | Positive direction | Negative direction |
|------|--------|--------------------|--------------------|
| Y    | Blue   | Solid dashed line  | Faint dotted line  |
| X    | Green  | Solid dashed line  | Faint dotted line  |

### Constructing Points

Once the axes are defined, the **dockable panel** (right side by default) becomes active:

1. Enter the **Y offset** (metres along the Y-axis from origin).
2. Enter the **X offset** (metres along the X-axis from origin).
3. Click **Construct Point** (or press **Enter**).

The plugin places a red **×** marker at the computed map position and draws:

- A **blue dashed line** from the origin along the Y-axis to the projection point.
- A **green dashed line** from the projection point perpendicular to the constructed point.
- A small white **□** at the right-angle corner.
- A compact **label** showing the offset values.

You can construct as many points as you need. Each point is added to the results table in the panel.

### Exporting Points

Click **Export to Layer** to create a temporary **memory layer** named *"Orthogonal Measure Points"* containing all constructed points with the following attributes:

| Field      | Type   | Description                    |
|------------|--------|--------------------------------|
| `id`       | Int    | Sequential point number        |
| `x_offset` | Double | X offset in metres             |
| `y_offset` | Double | Y offset in metres             |
| `map_e`    | Double | Easting in map CRS             |
| `map_n`    | Double | Northing in map CRS            |

The layer uses the current project CRS and can be saved to any spatial format (Shapefile, GeoPackage, etc.) using standard QGIS tools.

---

## User Interface

### Toolbar & Menu

- **Toolbar icon:** Click the Orthogonal Measure icon or go to **Plugins → Orthogonal Measure**.
- The map tool activates, and the dockable panel opens.

### Dockable Panel

The panel can be:

- **Docked** to the left, right, top, or bottom of the QGIS window.
- **Tabbed** alongside Layers, Browser, or any other panel.
- **Floated** as an independent window.

#### Panel Sections

| Section              | Description                                                    |
|----------------------|----------------------------------------------------------------|
| **Status**           | Instructions and status messages; shows origin and Y-axis coords once defined. |
| **Enter offset (m)** | Y and X spinboxes (range ±999 999 m, 3 decimal places, 0.1 m step). |
| **Constructed Points** | Table listing all constructed points with offsets and map coords. |
| **Buttons**          | *Reset* — clear everything. *Export to Layer* — export points.  |

### Keyboard Shortcuts

| Key     | Action                                                  |
|---------|---------------------------------------------------------|
| Enter   | Construct point (when a spinbox is focused)             |
| Escape  | Reset the tool (clear axes and all points on the canvas) |

### Snapping

When the map tool is active, **vertex + segment snapping** is automatically enabled on all layers with a 20 px tolerance. This lets you precisely snap the origin or Y-axis point to existing features. The previous snapping configuration is restored when the tool is deactivated.

---

## Visual Feedback

All visual elements are drawn directly on the map canvas and automatically reposition when you pan or zoom.

| Element               | Appearance                                    |
|-----------------------|-----------------------------------------------|
| Origin marker         | Red double-triangle, 12 px                    |
| Y-axis point marker   | Blue triangle, 10 px                          |
| Y-axis (positive)     | Blue dashed line, 2 px                        |
| Y-axis (negative)     | Blue dotted line, 1 px, faded                 |
| X-axis (positive)     | Green dashed line, 2 px                       |
| X-axis (negative)     | Green dotted line, 1 px, faded                |
| Constructed point     | Red ×, 12 px                                  |
| Y projection line     | Blue dashed, origin → Y-axis projection       |
| X projection line     | Green dashed, projection → constructed point  |
| Right-angle indicator | White □, 6 px at the corner                   |
| Offset label          | Compact text with white background and border |

---

## Typical Workflow

```
1.  Open your project in QGIS (any CRS).
2.  Click the Orthogonal Measure toolbar icon.
3.  Click on a known point on the map → origin is set (red marker).
4.  Click a second point that defines the Y-direction (blue marker).
    → Axes appear on the canvas; the panel becomes active.
5.  Enter Y = 10.000, X = 0.000 → click Construct Point.
    → A point is placed 10 m along the Y-axis.
6.  Enter Y = 5.000, X = -3.500 → click Construct Point.
    → A point is placed 5 m along Y and 3.5 m to the left of Y.
7.  Repeat for all needed points.
8.  Click Export to Layer → memory layer is added to the project.
9.  Right-click the layer → Export → Save As… to save permanently.
10. Close the panel or press Reset to start a new measurement.
```

---

## Technical Details

- **CRS handling:** Offsets are in ground metres. The plugin uses `QgsDistanceArea` with the project ellipsoid to convert between map-CRS units and ground distances, so it works accurately in EPSG:3857, UTM zones, state planes, and even geographic CRS.
- **Axis vectors:** Internally computed as unit vectors scaled so that 1.0 = 1 ground metre. The X-axis is the Y-axis rotated 90° clockwise: `(a, b) → (b, -a)`.
- **Canvas items:** All markers, rubber bands, and labels are `QgsMapCanvasItem` objects that reposition on pan/zoom. Labels use a fixed pixel size for consistent readability.
- **Memory layer export:** Uses the QGIS memory provider (`"memory"`). The layer inherits the project CRS.

---

## Installation

### From ZIP

1. Download the plugin ZIP archive.
2. In QGIS, go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the ZIP file and click **Install**.

### Manual

1. Copy the `orthogonal_measure` folder to your QGIS plugins directory:
   - **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
2. Restart QGIS (or reload plugins).
3. Enable *Orthogonal Measure* in **Plugins → Manage and Install Plugins**.

---

## File Structure

```
orthogonal_measure/
├── __init__.py                        # Plugin entry point (classFactory)
├── orthogonal_measure.py              # Main plugin class (OrthogonalMeasure)
├── ortho_map_tool.py                  # Map tool + canvas items (OrthogonalMapTool, MapTextLabel)
├── orthogonal_measure_dialog.py       # Dockable panel (OrthogonalMeasureDialog)
├── orthogonal_measure_dialog_base.ui  # Qt Designer UI form
├── resources.py                       # Compiled Qt resources (icon)
├── resources.qrc                      # Qt resource definition
├── metadata.txt                       # QGIS plugin metadata
├── icon.png                           # Plugin icon
├── README.md                          # This file
├── README.html                        # HTML version of this documentation
└── i18n/                              # Translations
```

---

## Known Limitations

- The export creates a **temporary memory layer** — it must be saved manually to persist.
- The plugin does not support entering offsets in units other than metres.
- Axis lines have a fixed visual length (1.5 × the distance between origin and Y-axis point).

---

## License

This program is free software; you can redistribute it and/or modify it under the terms of the **GNU General Public License** as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.

---

© 2026 Darko Nedic — [office@geo-biz.com](mailto:office@geo-biz.com)
