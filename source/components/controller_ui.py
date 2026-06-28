"""Controller UI: hint icons inside buttons and action router."""
import os
import time
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from .. import config, paths
from ..controller import (
    AXIS_LEFTY,
    BUTTON_SOUTH, BUTTON_EAST, BUTTON_WEST, BUTTON_NORTH,
    BUTTON_BACK, BUTTON_START,
    BUTTON_LEFT_SHOULDER, BUTTON_RIGHT_SHOULDER,
    is_playstation_type,
)

ICON_SIZE = 20

_BUTTON_NAMES = {
    BUTTON_SOUTH: "SOUTH",
    BUTTON_EAST: "EAST",
    BUTTON_WEST: "WEST",
    BUTTON_NORTH: "NORTH",
    BUTTON_BACK: "select",
    BUTTON_START: "start",
    BUTTON_LEFT_SHOULDER: "LEFT_SHOULDER",
    BUTTON_RIGHT_SHOULDER: "RIGHT_SHOULDER",
}


class ControllerButtonIcon:
    def __init__(
        self, button: QPushButton, button_enum: int, controller_mgr
    ) -> None:
        self._button = button
        self._button_enum = button_enum
        self._controller_mgr = controller_mgr
        self._use_ps = False
        self._simple = config.controller_simple_icons
        self._visible = False
        self._icon = QIcon()

        button.setIconSize(QSize(0, 0))
        button.setIcon(QIcon())

        controller_mgr.activity_changed.connect(self._on_activity_changed)
        controller_mgr.connected.connect(self._on_connected)

        gp_type = controller_mgr.gamepad_type
        self._use_ps = is_playstation_type(gp_type) or controller_mgr.has_ps_labels()
        self._load_icon()

    def _load_icon(self) -> None:
        name = _BUTTON_NAMES.get(self._button_enum)
        if name is None:
            self._icon = QIcon()
            return

        base = os.path.join(paths.BASE_DIR, "assets", "controller")
        if self._simple:
            base = os.path.join(base, "simple")

        subfolder = "ps" if self._use_ps else "xbox"
        filename = f"{name}.png"

        for candidate in (
            os.path.join(base, subfolder, filename),
            os.path.join(base, filename),
        ):
            if os.path.exists(candidate):
                pm = QPixmap(candidate)
                if not pm.isNull():
                    scaled = pm.scaled(
                        ICON_SIZE, ICON_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._icon = QIcon(scaled)
                    return

        self._icon = QIcon()

    def _on_activity_changed(self, active: bool) -> None:
        self._visible = active
        if active and not self._icon.isNull():
            self._button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            self._button.setIcon(self._icon)
        else:
            self._button.setIcon(QIcon())
            self._button.setIconSize(QSize(0, 0))

    def _on_connected(self, name: str, gp_type: int) -> None:
        self._use_ps = is_playstation_type(gp_type) or self._controller_mgr.has_ps_labels()
        self._load_icon()
        if self._visible:
            self._button.setIcon(self._icon)

    def set_simple_mode(self, enabled: bool) -> None:
        self._simple = enabled
        self._load_icon()
        if self._visible:
            self._button.setIcon(self._icon)

    def cleanup(self) -> None:
        try:
            self._controller_mgr.activity_changed.disconnect(self._on_activity_changed)
        except Exception:
            pass
        try:
            self._controller_mgr.connected.disconnect(self._on_connected)
        except Exception:
            pass


class ControllerRouter:
    def __init__(self, controller_mgr) -> None:
        self._controller_mgr = controller_mgr
        self._registry: list[tuple[QWidget, dict[int, callable]]] = []
        self._global_actions: dict[int, callable] = {}
        self._modal_override: Optional[dict[int, callable]] = None

        self._regions: list[tuple[QWidget, dict[int, callable], int]] = []
        self._focus_order: list[QWidget] = []
        self._focus_index = -1

        controller_mgr.button_down.connect(self._route)

    def cleanup(self) -> None:
        try:
            self._controller_mgr.button_down.disconnect(self._route)
        except Exception:
            pass

    def register(self, widget: QWidget, actions: dict[int, callable]) -> None:
        self._registry.append((widget, actions))

    def register_global(self, actions: dict[int, callable]) -> None:
        self._global_actions.update(actions)

    def unregister_global(self, *buttons: int) -> None:
        for btn in buttons:
            self._global_actions.pop(btn, None)

    def unregister(self, widget: QWidget) -> None:
        self._registry = [(w, a) for w, a in self._registry if w is not widget]

    def set_modal_override(self, actions: dict[int, callable]) -> None:
        self._modal_override = actions

    def clear_modal_override(self) -> None:
        self._modal_override = None

    def register_focus_region(self, widget: QWidget, actions: dict[int, callable], order: int = 0) -> None:
        self._regions.append((widget, actions, order))
        self._regions.sort(key=lambda x: x[2])

    def _route(self, button: int) -> None:
        override = self._modal_override
        if override and button in override:
            override[button]()
            return
        if button in self._global_actions:
            self._global_actions[button]()
            return

        focused = QApplication.focusWidget()
        for widget, actions in self._registry:
            if focused and (widget is focused or widget.isAncestorOf(focused) or focused.isAncestorOf(widget)):
                if button in actions:
                    actions[button]()
                    return

        if not focused:
            for widget, actions in self._regions:
                if button in actions:
                    actions[button]()
                    return


class FocusOverlay(QWidget):
    def __init__(self, target: QWidget) -> None:
        super().__init__(target)
        self._color = QColor(0, 0, 0, 80)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        target.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.parent() and event.type() == QEvent.Resize:
            self._reposition()
        return super().eventFilter(obj, event)

    def _reposition(self) -> None:
        p = self.parent()
        if p:
            self.setGeometry(p.rect())
            self.raise_()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)

    def show(self) -> None:
        self._reposition()
        super().show()
        self.update()


_AXIS_THRESHOLD = 14000
_AXIS_INITIAL_MS = 180
_AXIS_MIN_MS = 30
_AXIS_ACCEL = 40  # ms faster per second held


class AxisScroller:
    def __init__(self, scroll_fn: callable, parent: QObject = None) -> None:
        self._scroll_fn = scroll_fn
        self._timer = QTimer(parent)
        self._timer.timeout.connect(self._tick)
        self._dir = 0
        self._started_at = 0.0
        self._interval = 0

    def handle_axis(self, axis_idx: int, val: int) -> None:
        if axis_idx != AXIS_LEFTY:
            return
        if abs(val) < _AXIS_THRESHOLD:
            if self._dir:
                self._dir = 0
                self._timer.stop()
            return
        new_dir = -1 if val < 0 else 1
        if new_dir != self._dir:
            self._dir = new_dir
            self._started_at = time.monotonic()
            self._interval = _AXIS_INITIAL_MS
            self._timer.start(_AXIS_INITIAL_MS)
            self._scroll_fn(new_dir)

    def _tick(self) -> None:
        if not self._dir:
            return
        elapsed = time.monotonic() - self._started_at
        interval = max(_AXIS_MIN_MS, _AXIS_INITIAL_MS - int(elapsed * _AXIS_ACCEL))
        if interval != self._interval:
            self._interval = interval
            self._timer.setInterval(interval)
        self._scroll_fn(self._dir)

    def stop(self) -> None:
        self._dir = 0
        self._timer.stop()
