# -*- coding: utf-8 -*-
"""
Custom QgsMapTool for capturing two reference points that define
an orthogonal coordinate system on the map canvas.

Point 1 = origin (0,0)
Point 2 = defines the positive Y-axis direction
X-axis = perpendicular to Y-axis (rotated 90° clockwise)
"""

import math
from typing import List, Optional, Tuple

from qgis.PyQt.QtCore import pyqtSignal, Qt, QPointF, QRectF
from qgis.PyQt.QtGui import QColor, QCursor, QFont, QFontMetrics, QPen
from qgis.core import (
    Qgis,
    QgsDistanceArea,
    QgsPointLocator,
    QgsPointXY,
    QgsProject,
    QgsSnappingConfig,
    QgsTolerance,
    QgsWkbTypes,
)
from qgis.gui import (
    QgsMapCanvasItem,
    QgsMapTool,
    QgsRubberBand,
    QgsSnapIndicator,
    QgsVertexMarker,
)

# ---------------------------------------------------------------------------
#  Visual constants
# ---------------------------------------------------------------------------

COLOR_ORIGIN = QColor(255, 0, 0)
COLOR_Y_AXIS = QColor(0, 100, 255)
COLOR_X_AXIS = QColor(0, 180, 0)

COLOR_Y_AXIS_SOLID = QColor(0, 100, 255, 200)
COLOR_X_AXIS_SOLID = QColor(0, 180, 0, 200)
COLOR_Y_AXIS_FADED = QColor(0, 100, 255, 80)
COLOR_X_AXIS_FADED = QColor(0, 180, 0, 80)

COLOR_Y_PROJ = QColor(0, 100, 255, 180)
COLOR_X_PROJ = QColor(0, 180, 0, 180)

COLOR_RESULT = QColor(255, 50, 50)
COLOR_CORNER = QColor(255, 255, 255, 180)
COLOR_LABEL_BG = QColor(255, 255, 255, 200)

SNAP_TOLERANCE_PX = 20
AXIS_LENGTH_FACTOR = 1.5

ORIGIN_MARKER_SIZE = 12
YAXIS_MARKER_SIZE = 10
RESULT_MARKER_SIZE = 12
CORNER_MARKER_SIZE = 6

LABEL_FONT = QFont("Arial", 7)
LABEL_FONT.setStyleStrategy(QFont.PreferAntialias)
LABEL_OFFSET_X = 10
LABEL_OFFSET_Y = -8
LABEL_PADDING = 3
LABEL_LINE_SPACING = 1
COLOR_LABEL_BORDER = QColor(160, 160, 160, 180)

# Tool states
STATE_WAITING_ORIGIN = 0
STATE_WAITING_YAXIS = 1
STATE_AXES_DEFINED = 2

# Type alias
AxisVectors = Tuple[Tuple[float, float], Tuple[float, float]]


# ---------------------------------------------------------------------------
#  MapTextLabel
# ---------------------------------------------------------------------------


class MapTextLabel(QgsMapCanvasItem):
    """Compact multi-line text label anchored to a map coordinate.

    The label always renders at a **fixed pixel size** regardless of the
    current zoom level.  It repositions when the map is panned / zoomed
    but never rescales, so labels remain small and readable.
    """

    def __init__(
        self,
        canvas,
        map_point: QgsPointXY,
        lines: List[str],
        colors: Optional[List[QColor]] = None,
        font: Optional[QFont] = None,
        offset_x: int = LABEL_OFFSET_X,
        offset_y: int = LABEL_OFFSET_Y,
    ):
        super().__init__(canvas)
        self._canvas = canvas
        self._map_point = map_point
        self._lines = lines if isinstance(lines, list) else [lines]
        self._colors = colors or [QColor(0, 0, 0)]
        self._font = font or LABEL_FONT
        self._offset_x = offset_x
        self._offset_y = offset_y

        fm = QFontMetrics(self._font)
        self._line_height = fm.height()
        max_width = max(
            (fm.horizontalAdvance(line) for line in self._lines), default=40
        )
        total_height = (
            self._line_height * len(self._lines)
            + LABEL_LINE_SPACING * max(len(self._lines) - 1, 0)
        )

        self._rect_width = max_width + 2 * LABEL_PADDING
        self._rect_height = total_height + 2 * LABEL_PADDING

        self.updatePosition()

    # -- QgsMapCanvasItem overrides ------------------------------------------

    def updatePosition(self):
        """Reproject the map point to canvas pixels (no rescaling)."""
        self.setPos(self.toCanvasCoordinates(self._map_point))
        # Fixed pixel size — no setScale(); label stays the same size at
        # every zoom level.

    def boundingRect(self) -> QRectF:
        margin = 80
        return QRectF(
            self._offset_x - margin,
            self._offset_y - margin,
            self._rect_width + 2 * margin,
            self._rect_height + 2 * margin,
        )

    def paint(self, painter, _option, _widget=None):
        painter.setRenderHint(painter.Antialiasing, True)
        painter.setRenderHint(painter.TextAntialiasing, True)
        painter.setFont(self._font)

        bg_rect = QRectF(
            self._offset_x - LABEL_PADDING,
            self._offset_y - LABEL_PADDING,
            self._rect_width,
            self._rect_height,
        )
        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(COLOR_LABEL_BG)
        painter.drawRoundedRect(bg_rect, 2, 2)
        # Thin border
        painter.setPen(QPen(COLOR_LABEL_BORDER, 0.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(bg_rect, 2, 2)

        # Draw each line
        for idx, text in enumerate(self._lines):
            color = self._colors[idx % len(self._colors)]
            painter.setPen(QPen(color))
            y = (
                self._offset_y
                + LABEL_PADDING
                + self._line_height * (idx + 1)
                - 2
                + LABEL_LINE_SPACING * idx
            )
            painter.drawText(QPointF(self._offset_x, y), text)


# ---------------------------------------------------------------------------
#  OrthogonalMapTool
# ---------------------------------------------------------------------------


class OrthogonalMapTool(QgsMapTool):
    """Map tool for capturing two clicks that define an orthogonal system."""

    points_captured = pyqtSignal(QgsPointXY, QgsPointXY)
    tool_reset = pyqtSignal()

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.origin: Optional[QgsPointXY] = None
        self.y_axis_point: Optional[QgsPointXY] = None
        self.state: int = STATE_WAITING_ORIGIN

        # Visual items managed by this tool
        self._markers: List[QgsVertexMarker] = []
        self._rubber_bands: List[QgsRubberBand] = []
        self._result_markers: List[QgsVertexMarker] = []
        self._text_items: List[MapTextLabel] = []

        self._snap_indicator = QgsSnapIndicator(canvas)
        self._saved_snap_config: Optional[QgsSnappingConfig] = None

        self.setCursor(QCursor(Qt.CrossCursor))

    # ---- Snapping helpers --------------------------------------------------

    def _enable_snapping(self):
        """Activate vertex+segment snapping on all layers, saving the
        previous project config so it can be restored later.
        """
        project = QgsProject.instance()
        self._saved_snap_config = QgsSnappingConfig(project.snappingConfig())

        cfg = project.snappingConfig()
        cfg.setEnabled(True)
        cfg.setMode(QgsSnappingConfig.AllLayers)
        cfg.setUnits(QgsTolerance.Pixels)
        cfg.setTolerance(SNAP_TOLERANCE_PX)
        cfg.setIntersectionSnapping(True)
        self._set_snap_type(cfg)

        project.setSnappingConfig(cfg)
        self.canvas.snappingUtils().setConfig(cfg)

    @staticmethod
    def _set_snap_type(cfg: QgsSnappingConfig):
        """Set vertex+segment snapping, handling QGIS API variations."""
        try:
            cfg.setTypeFlag(
                Qgis.SnappingTypes(
                    Qgis.SnappingType.Vertex | Qgis.SnappingType.Segment
                )
            )
        except (AttributeError, TypeError):
            try:
                cfg.setType(QgsSnappingConfig.VertexAndSegment)
            except AttributeError:
                cfg.setType(2)

    def _restore_snapping(self):
        """Restore the snapping config saved by ``_enable_snapping``."""
        if self._saved_snap_config is None:
            return
        project = QgsProject.instance()
        project.setSnappingConfig(self._saved_snap_config)
        self.canvas.snappingUtils().setConfig(self._saved_snap_config)
        self._saved_snap_config = None

    def _snap_point(self, event_pos) -> QgsPointXY:
        """Snap the screen position to a nearby vertex, falling back
        to the plain map coordinate.
        """
        match = self.canvas.snappingUtils().snapToMap(event_pos)
        if match.isValid():
            return QgsPointXY(match.point())
        return self.toMapCoordinates(event_pos)

    # ---- Canvas-item helpers -----------------------------------------------

    def _add_marker(
        self,
        point: QgsPointXY,
        color: QColor = COLOR_ORIGIN,
        size: int = 10,
        icon_type: int = QgsVertexMarker.ICON_CIRCLE,
        pen_width: int = 2,
    ) -> QgsVertexMarker:
        """Create a vertex marker, track it, and return it."""
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(point)
        marker.setColor(color)
        marker.setIconSize(size)
        marker.setIconType(icon_type)
        marker.setPenWidth(pen_width)
        self._markers.append(marker)
        return marker

    def _add_rubber_band(
        self,
        points: List[QgsPointXY],
        color: QColor,
        width: int = 2,
        line_style: int = Qt.DashLine,
    ) -> QgsRubberBand:
        """Create a line rubber band and track it for later cleanup."""
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        rb.setColor(color)
        rb.setWidth(width)
        rb.setLineStyle(line_style)
        for pt in points:
            rb.addPoint(pt)
        self._rubber_bands.append(rb)
        return rb

    # ---- Geometry helpers --------------------------------------------------

    def _distance_area(self) -> QgsDistanceArea:
        """Return a configured ``QgsDistanceArea`` for the current project."""
        da = QgsDistanceArea()
        project = QgsProject.instance()
        da.setSourceCrs(project.crs(), project.transformContext())
        da.setEllipsoid(project.ellipsoid())
        return da

    def _axis_endpoint(
        self, unit: Tuple[float, float], length: float, negative: bool = False
    ) -> QgsPointXY:
        """Compute an axis endpoint from the origin."""
        sign = -1.0 if negative else 1.0
        return QgsPointXY(
            self.origin.x() + sign * unit[0] * length,
            self.origin.y() + sign * unit[1] * length,
        )

    # ---- Axis drawing ------------------------------------------------------

    def _draw_axes(self):
        """Draw the four half-axes (Y+, Y-, X+, X-) from the origin."""
        if self.origin is None or self.y_axis_point is None:
            return

        y_unit, x_unit = self.axis_vectors()
        ground_dist = self._distance_area().measureLine(
            self.origin, self.y_axis_point
        )
        length = ground_dist * AXIS_LENGTH_FACTOR

        # Positive half-axes (solid dashed)
        self._add_rubber_band(
            [self.origin, self._axis_endpoint(y_unit, length)],
            COLOR_Y_AXIS_SOLID,
        )
        self._add_rubber_band(
            [self.origin, self._axis_endpoint(x_unit, length)],
            COLOR_X_AXIS_SOLID,
        )

        # Negative half-axes (thin dotted)
        self._add_rubber_band(
            [self.origin, self._axis_endpoint(y_unit, length, negative=True)],
            COLOR_Y_AXIS_FADED,
            width=1,
            line_style=Qt.DotLine,
        )
        self._add_rubber_band(
            [self.origin, self._axis_endpoint(x_unit, length, negative=True)],
            COLOR_X_AXIS_FADED,
            width=1,
            line_style=Qt.DotLine,
        )

    # ---- Public API --------------------------------------------------------

    def axis_vectors(self) -> AxisVectors:
        """Return ``(y_unit, x_unit)`` as tuples of length 2.

        Vectors are in map-CRS units scaled so that multiplying by 1.0
        moves exactly 1 metre on the ground (ellipsoidal distance).

        Y-axis: direction from *origin* to *y_axis_point*.
        X-axis: Y-axis rotated 90 deg clockwise.
        """
        if self.origin is None or self.y_axis_point is None:
            return (0.0, 1.0), (1.0, 0.0)

        dx = self.y_axis_point.x() - self.origin.x()
        dy = self.y_axis_point.y() - self.origin.y()
        map_length = math.hypot(dx, dy)
        if map_length == 0:
            return (0.0, 1.0), (1.0, 0.0)

        ground_distance = self._distance_area().measureLine(
            self.origin, self.y_axis_point
        )
        if ground_distance == 0:
            return (0.0, 1.0), (1.0, 0.0)

        # map-CRS units per 1 ground metre
        scale = map_length / ground_distance
        y_unit = (dx / map_length * scale, dy / map_length * scale)
        x_unit = (y_unit[1], -y_unit[0])  # 90 deg clockwise
        return y_unit, x_unit

    def compute_point(self, x_val: float, y_val: float) -> QgsPointXY:
        """Compute the map point for the given orthogonal offsets (metres)."""
        y_unit, x_unit = self.axis_vectors()
        return QgsPointXY(
            self.origin.x() + x_val * x_unit[0] + y_val * y_unit[0],
            self.origin.y() + x_val * x_unit[1] + y_val * y_unit[1],
        )

    def add_result_marker(
        self, point: QgsPointXY, x_val: float = 0.0, y_val: float = 0.0
    ) -> QgsVertexMarker:
        """Place a marker with projection lines and dimension labels."""
        # Main result marker
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(point)
        marker.setColor(COLOR_RESULT)
        marker.setIconSize(RESULT_MARKER_SIZE)
        marker.setIconType(QgsVertexMarker.ICON_X)
        marker.setPenWidth(2)
        self._result_markers.append(marker)

        # Projection point on Y-axis
        y_unit, _x_unit = self.axis_vectors()
        y_proj = QgsPointXY(
            self.origin.x() + y_val * y_unit[0],
            self.origin.y() + y_val * y_unit[1],
        )

        # Projection lines
        self._add_rubber_band([self.origin, y_proj], COLOR_Y_PROJ)
        self._add_rubber_band([y_proj, point], COLOR_X_PROJ)

        # Right-angle corner indicator
        corner = QgsVertexMarker(self.canvas)
        corner.setCenter(y_proj)
        corner.setColor(COLOR_CORNER)
        corner.setIconSize(CORNER_MARKER_SIZE)
        corner.setIconType(QgsVertexMarker.ICON_BOX)
        corner.setPenWidth(1)
        self._result_markers.append(corner)

        # Compact label — alternate offset direction to reduce overlap
        point_index = len(self._result_markers)
        if point_index % 2 == 0:
            off_x, off_y = LABEL_OFFSET_X, LABEL_OFFSET_Y
        else:
            off_x, off_y = LABEL_OFFSET_X, LABEL_OFFSET_Y + 22

        label = MapTextLabel(
            self.canvas,
            point,
            lines=[f"y={y_val:.3f}  x={x_val:.3f}"],
            colors=[QColor(50, 50, 50)],
            offset_x=off_x,
            offset_y=off_y,
        )
        self._text_items.append(label)

        self.canvas.refresh()
        return marker

    # ---- Reset / cleanup ---------------------------------------------------

    def _remove_items(self, items: list):
        """Remove a list of QGraphicsItem objects from the canvas scene."""
        scene = self.canvas.scene()
        for item in items:
            scene.removeItem(item)
        items.clear()

    def reset(self):
        """Clear everything and return to *waiting-for-origin* state."""
        self.origin = None
        self.y_axis_point = None
        self.state = STATE_WAITING_ORIGIN

        self._remove_items(self._markers)
        self._remove_items(self._rubber_bands)
        self._remove_items(self._result_markers)
        self._remove_items(self._text_items)

        self.canvas.refresh()
        self.tool_reset.emit()

    def clear_results(self):
        """Clear only constructed-point markers (keep reference axes)."""
        self._remove_items(self._result_markers)
        self._remove_items(self._text_items)
        self.canvas.refresh()

    # ---- QgsMapTool overrides ----------------------------------------------

    def activate(self):
        super().activate()
        self._enable_snapping()

    def canvasMoveEvent(self, event):
        if self.state >= STATE_AXES_DEFINED:
            return
        match = self.canvas.snappingUtils().snapToMap(event.pos())
        self._snap_indicator.setMatch(match)

    def canvasReleaseEvent(self, event):
        point = self._snap_point(event.pos())

        if self.state == STATE_WAITING_ORIGIN:
            self.origin = point
            self._add_marker(
                point, COLOR_ORIGIN, ORIGIN_MARKER_SIZE,
                QgsVertexMarker.ICON_DOUBLE_TRIANGLE,
            )
            self.state = STATE_WAITING_YAXIS

        elif self.state == STATE_WAITING_YAXIS:
            self.y_axis_point = point
            self._add_marker(
                point, COLOR_Y_AXIS, YAXIS_MARKER_SIZE,
                QgsVertexMarker.ICON_TRIANGLE,
            )
            self._draw_axes()
            self.state = STATE_AXES_DEFINED
            self._snap_indicator.setMatch(QgsPointLocator.Match())
            self.canvas.refresh()
            self.points_captured.emit(self.origin, self.y_axis_point)

    def deactivate(self):
        self._snap_indicator.setMatch(QgsPointLocator.Match())
        self._restore_snapping()
        super().deactivate()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._snap_indicator.setMatch(QgsPointLocator.Match())
            self.reset()
