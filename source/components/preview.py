"""Image and .anm2 preview popup widgets."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QMenu

from .. import config
from ..worker import WorkerThread


def _resolve_spritesheet(anm2_dir: str, ss_path: str) -> str | None:
    resource_root = anm2_dir
    parts = anm2_dir.split(os.sep)
    for i in range(len(parts), 0, -1):
        candidate = os.sep.join(parts[:i])
        gfx_dir = os.path.join(candidate, "gfx")
        if os.path.isdir(gfx_dir):
            resource_root = candidate
            break

    candidates = [
        os.path.join(resource_root, "gfx", ss_path),
        os.path.join(anm2_dir, ss_path),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    if os.name != "nt":
        for path in candidates:
            lower = path.lower()
            if os.path.exists(lower):
                return lower
        name_lower = os.path.basename(ss_path).lower()
        for dirpath, _dirnames, filenames in os.walk(resource_root):
            for f in filenames:
                if f.lower() == name_lower:
                    return os.path.join(dirpath, f)
    return None


def _load_preview_data(path: str):
    """Run in a worker thread — returns structured data or None."""
    lower = path.lower()
    if lower.endswith(".png"):
        img = QImage(path)
        if img.isNull():
            return None
        img = img.scaled(
            200, 200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        return ("png", img)

    if lower.endswith(".anm2"):
        try:
            tree = ET.parse(path)
        except Exception:
            return None
        root = tree.getroot()
        anm2_dir = os.path.dirname(path)

        if config.animate_anm2_preview:
            result = _parse_anm2_frames(root, anm2_dir)
            if result:
                frames_qimage, delays = result
                return ("anm2", frames_qimage, delays)

        try:
            ss = root.find(".//Spritesheet")
            sprite_path = (
                ss.get("Path", "").replace("\\", "/") if ss is not None else None
            )
            if not sprite_path:
                return None
            resolved = _resolve_spritesheet(anm2_dir, sprite_path)
            if not resolved:
                return None
            img = QImage(resolved)
            if img.isNull():
                return None
            img = img.scaled(
                200, 200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            return ("png", img)
        except Exception:
            return None

    return None


def _parse_anm2_frames(root, anm2_dir):
    """Parse .anm2 XML and composite frames as QImage list (thread-safe)."""
    spritesheets: dict[str, QImage] = {}
    for ss in root.findall(".//Spritesheet"):
        ss_id = ss.get("Id", "0")
        ss_path = ss.get("Path", "").replace("\\", "/")
        full_ss = _resolve_spritesheet(anm2_dir, ss_path)
        if full_ss:
            img = QImage(full_ss)
            if not img.isNull():
                spritesheets[ss_id] = img
    if not spritesheets:
        return None

    layer_sprite: dict[int, str] = {}
    for layer in root.findall(".//Content/Layers/Layer"):
        layer_sprite[int(layer.get("Id", "0"))] = layer.get("SpritesheetId", "0")

    anims = root.findall(".//Animations/Animation")
    if not anims:
        return None

    info = root.find(".//Info")
    anm2_fps = int(info.get("Fps", "30")) if info is not None else 30

    all_frames: list[tuple[list[tuple[int, int, QImage]], int]] = []
    first_min_x = first_min_y = 1_000_000
    first_max_x = first_max_y = -1_000_000

    for anim_idx, anim in enumerate(anims):
        root_frames = anim.findall("RootAnimation/Frame")

        layer_order: list[int] = []
        layer_anims: dict[int, list] = {}
        for la in anim.findall("LayerAnimations/LayerAnimation"):
            lid = int(la.get("LayerId", "0"))
            frames = la.findall("Frame")
            if frames and lid not in layer_anims:
                layer_anims[lid] = frames
                layer_order.append(lid)
        if not layer_anims:
            continue

        max_frames = max(
            max((len(f) for f in layer_anims.values()), default=0),
            len(root_frames),
        )

        for i in range(max_frames):
            rf = (
                root_frames[min(i, len(root_frames) - 1)]
                if root_frames
                else None
            )
            if rf is not None and rf.get("Visible", "true").lower() == "false":
                continue
            root_x = int(rf.get("XPosition", "0")) if rf is not None else 0
            root_y = int(rf.get("YPosition", "0")) if rf is not None else 0

            items: list[tuple[int, int, QImage]] = []
            for lid in layer_order:
                frames = layer_anims[lid]
                f = frames[min(i, len(frames) - 1)]
                if f.get("Visible", "true").lower() == "false":
                    continue

                x_pos = int(f.get("XPosition", "0"))
                y_pos = int(f.get("YPosition", "0"))
                xp = int(f.get("XPivot", "0"))
                yp = int(f.get("YPivot", "0"))
                w = int(f.get("Width", "0"))
                h = int(f.get("Height", "0"))
                if w == 0 or h == 0:
                    continue

                lx = root_x + x_pos - xp
                ly = root_y + y_pos - yp

                ss_img = spritesheets.get(layer_sprite.get(lid, "0"))
                if ss_img is None:
                    continue
                xcrop = int(f.get("XCrop", "0"))
                ycrop = int(f.get("YCrop", "0"))
                src = ss_img.copy(xcrop, ycrop, w, h)
                items.append((lx, ly, src))

                if anim_idx == 0:
                    rx = lx + w
                    by = ly + h
                    if lx < first_min_x:
                        first_min_x = lx
                    if ly < first_min_y:
                        first_min_y = ly
                    if rx > first_max_x:
                        first_max_x = rx
                    if by > first_max_y:
                        first_max_y = by

            if not items:
                continue

            delay = 1
            for lid in layer_order:
                frames = layer_anims[lid]
                if i < len(frames):
                    delay = max(delay, int(frames[i].get("Delay", "1")))
            all_frames.append((items, delay))

    if not all_frames or first_min_x == 1_000_000:
        return None

    cw = max(int(first_max_x - first_min_x), 1)
    ch = max(int(first_max_y - first_min_y), 1)
    ox = int(first_min_x)
    oy = int(first_min_y)

    frames_qimage: list[QImage] = []
    delays: list[int] = []

    for frame_items, raw_delay in all_frames:
        canvas = QImage(cw, ch, QImage.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        for lx, ly, src in frame_items:
            painter.drawImage(lx - ox, ly - oy, src)
        painter.end()
        frames_qimage.append(canvas)
        delays.append(max(int(raw_delay * 1000 / anm2_fps), 16))

    return frames_qimage, delays


class PreviewWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(
            parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self.setStyleSheet(f"border: 1px solid {config.preview_border or 'palette(mid)'}; background: {config.preview_bg or 'palette(base)'}; padding: 2px;")
        self.hide()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._path: str | None = None
        self._anm2_timer = QTimer(self)
        self._anm2_timer.timeout.connect(self._anm2_next_frame)
        self._anm2_frames: list[QPixmap] = []
        self._anm2_delays: list[int] = []
        self._anm2_index: int = 0

        self._request_id: int = 0
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_fire)
        self._worker: WorkerThread | None = None
        self._pending_path: str | None = None
        self._pending_pos: QPoint | None = None
        self._zombie_workers: list[WorkerThread] = []

    def stop(self) -> None:
        self._request_id += 1
        self._debounce_timer.stop()
        self._pending_path = None
        self._pending_pos = None
        self._cancel_worker()
        self._anm2_timer.stop()
        self._anm2_frames.clear()
        self._anm2_delays.clear()
        self._anm2_index = 0
        self.hide()

    def _cancel_worker(self) -> None:
        if self._worker is not None:
            self._zombie_workers.append(self._worker)
            self._worker = None
        self._sweep_zombies()

    def _sweep_zombies(self) -> None:
        alive = []
        for w in self._zombie_workers:
            try:
                if w.isRunning():
                    alive.append(w)
            except RuntimeError:
                pass
        self._zombie_workers = alive

    def _on_debounce_fire(self) -> None:
        if self._pending_path is not None and self._pending_pos is not None:
            self._start_worker(self._pending_path, self._pending_pos)

    def show_preview(
        self, file_path: str, global_pos: QPoint, debounce: bool = True
    ) -> bool:
        lower = file_path.lower()
        if not lower.endswith((".png", ".anm2")):
            return False
        if not os.path.exists(file_path):
            return False

        self._request_id += 1
        self._debounce_timer.stop()
        self._pending_path = None
        self._pending_pos = None
        self.hide()
        self._anm2_timer.stop()
        self._anm2_frames.clear()
        self._anm2_delays.clear()
        self._anm2_index = 0

        if debounce:
            self._pending_path = file_path
            self._pending_pos = global_pos
            self._debounce_timer.start(50)
            return True

        self._start_worker(file_path, global_pos)
        return True

    def _start_worker(self, file_path: str, global_pos: QPoint) -> None:
        self._cancel_worker()
        self._path = file_path
        req_id = self._request_id
        worker = WorkerThread(_load_preview_data, file_path)
        worker.finished.connect(
            lambda result: self._on_preview_ready(req_id, result, global_pos)
        )
        worker.error.connect(lambda err: None)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_preview_ready(
        self, req_id: int, result, global_pos: QPoint
    ) -> None:
        if req_id != self._request_id:
            return
        self._worker = None

        if result is None:
            return

        kind = result[0]
        if kind == "png":
            img = result[1]
            pix = QPixmap.fromImage(img)
            if pix.isNull():
                return
            self.setPixmap(pix)
            self.adjustSize()
            self.move(global_pos + QPoint(15, 15))
            self.show()
        elif kind == "anm2":
            frames_qimage, delays = result[1], result[2]
            if not frames_qimage:
                return
            self._anm2_frames = [QPixmap.fromImage(img) for img in frames_qimage]
            self._anm2_delays = delays
            self._anm2_index = 0
            scaled = self._anm2_frames[0].scaled(
                200,
                200,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self.setPixmap(scaled)
            self.adjustSize()
            if len(self._anm2_frames) > 1:
                self._anm2_timer.start(self._anm2_delays[0])
            self.move(global_pos + QPoint(15, 15))
            self.show()

    def _anm2_next_frame(self) -> None:
        if not self._anm2_frames:
            return
        self._anm2_index = (self._anm2_index + 1) % len(self._anm2_frames)
        scaled = self._anm2_frames[self._anm2_index].scaled(
            200,
            200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.setPixmap(scaled)
        self.adjustSize()
        self._anm2_timer.setInterval(self._anm2_delays[self._anm2_index])

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        action = QAction("Animate .anm2 preview", self)
        action.setCheckable(True)
        action.setChecked(config.animate_anm2_preview)
        action.toggled.connect(self._toggle_animate)
        menu.addAction(action)
        menu.exec(self.mapToGlobal(pos))

    def _toggle_animate(self, checked: bool) -> None:
        config.animate_anm2_preview = checked
        config.save()
