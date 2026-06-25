import os
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QMenu

from .. import config


class PreviewWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("border: 1px solid #888; background: #fff; padding: 2px;")
        self.hide()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._path: str | None = None
        self._anm2_timer = QTimer(self)
        self._anm2_timer.timeout.connect(self._anm2_next_frame)
        self._anm2_frames: list[QPixmap] = []
        self._anm2_delays: list[int] = []
        self._anm2_index: int = 0

    def _resolve_spritesheet(self, anm2_dir: str, ss_path: str) -> str | None:
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

    def stop(self) -> None:
        self._anm2_timer.stop()
        self._anm2_frames.clear()
        self._anm2_delays.clear()
        self._anm2_index = 0
        self.hide()

    def show_preview(self, file_path: str, global_pos: QPoint) -> bool:
        self.stop()
        lower = file_path.lower()
        if not lower.endswith((".png", ".anm2")):
            return False
        if not os.path.exists(file_path):
            return False

        if lower.endswith(".anm2"):
            if config.animate_anm2_preview:
                self._path = file_path
                if self._parse_anm2_and_start(file_path, global_pos):
                    return True
            try:
                tree = ET.parse(file_path)
                ss = tree.getroot().find(".//Spritesheet")
                sprite_path = ss.get("Path", "").replace("\\", "/") if ss is not None else None
                if not sprite_path:
                    return False
                resolved = self._resolve_spritesheet(os.path.dirname(file_path), sprite_path)
                if not resolved:
                    return False
                file_path = resolved
            except Exception:
                return False

        if self._path != file_path:
            pix = QPixmap(file_path)
            if pix.isNull():
                return False
            scaled = pix.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.setPixmap(scaled)
            self.adjustSize()
            self._path = file_path

        self.move(global_pos + QPoint(15, 15))
        self.show()
        return True

    def _parse_anm2_and_start(self, anm2_path: str, global_pos: QPoint) -> bool:
        try:
            tree = ET.parse(anm2_path)
            root = tree.getroot()
            anm2_dir = os.path.dirname(anm2_path)

            spritesheets: dict[str, QPixmap] = {}
            for ss in root.findall(".//Spritesheet"):
                ss_id = ss.get("Id", "0")
                ss_path = ss.get("Path", "").replace("\\", "/")
                full_ss = self._resolve_spritesheet(anm2_dir, ss_path)
                if full_ss:
                    pix = QPixmap(full_ss)
                    if not pix.isNull():
                        spritesheets[ss_id] = pix
            if not spritesheets:
                return False

            layer_sprite: dict[int, str] = {}
            for layer in root.findall(".//Content/Layers/Layer"):
                layer_sprite[int(layer.get("Id", "0"))] = layer.get("SpritesheetId", "0")

            anims = root.findall(".//Animations/Animation")
            if not anims:
                return False

            info = root.find(".//Info")
            anm2_fps = int(info.get("Fps", "30")) if info is not None else 30

            all_frames: list[tuple[list[tuple[int, int, QPixmap]], int]] = []
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
                    rf = root_frames[min(i, len(root_frames) - 1)] if root_frames else None
                    if rf is not None and rf.get("Visible", "true").lower() == "false":
                        continue
                    root_x = int(rf.get("XPosition", "0")) if rf is not None else 0
                    root_y = int(rf.get("YPosition", "0")) if rf is not None else 0

                    items: list[tuple[int, int, QPixmap]] = []
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

                        ss_pix = spritesheets.get(layer_sprite.get(lid, "0"))
                        if ss_pix is None:
                            continue
                        xcrop = int(f.get("XCrop", "0"))
                        ycrop = int(f.get("YCrop", "0"))
                        src = ss_pix.copy(xcrop, ycrop, w, h)
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

            if not all_frames:
                return False

            if first_min_x == 1_000_000:
                cw = ch = 1
                ox = oy = 0
            else:
                cw = max(int(first_max_x - first_min_x), 1)
                ch = max(int(first_max_y - first_min_y), 1)
                ox = int(first_min_x)
                oy = int(first_min_y)

            self._anm2_frames.clear()
            self._anm2_delays.clear()

            for frame_items, raw_delay in all_frames:
                canvas = QPixmap(cw, ch)
                canvas.fill(Qt.GlobalColor.transparent)
                painter = QPainter(canvas)
                for lx, ly, src in frame_items:
                    painter.drawPixmap(lx - ox, ly - oy, src)
                painter.end()
                self._anm2_frames.append(canvas)
                self._anm2_delays.append(max(int(raw_delay * 1000 / anm2_fps), 16))

            self._anm2_index = 0
            scaled = self._anm2_frames[0].scaled(
                200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
            )
            self.setPixmap(scaled)
            self.adjustSize()
            if len(self._anm2_frames) > 1:
                self._anm2_timer.start(self._anm2_delays[0])
            self.move(global_pos + QPoint(15, 15))
            self.show()
            return True
        except Exception:
            return False

    def _anm2_next_frame(self) -> None:
        if not self._anm2_frames:
            return
        self._anm2_index = (self._anm2_index + 1) % len(self._anm2_frames)
        scaled = self._anm2_frames[self._anm2_index].scaled(
            200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
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
