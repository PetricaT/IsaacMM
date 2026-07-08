"""Controller support via SDL3 gamepad API."""

from __future__ import annotations

import ctypes
import enum
import os
import threading
from typing import Optional

import sdl3
from PySide6.QtCore import QObject, QTimer, Signal


class GamepadType(enum.IntEnum):
    UNKNOWN = sdl3.SDL_GAMEPAD_TYPE_UNKNOWN
    STANDARD = sdl3.SDL_GAMEPAD_TYPE_STANDARD
    XBOX360 = sdl3.SDL_GAMEPAD_TYPE_XBOX360
    XBOXONE = sdl3.SDL_GAMEPAD_TYPE_XBOXONE
    PS3 = sdl3.SDL_GAMEPAD_TYPE_PS3
    PS4 = sdl3.SDL_GAMEPAD_TYPE_PS4
    PS5 = sdl3.SDL_GAMEPAD_TYPE_PS5
    NINTENDO_SWITCH_PRO = sdl3.SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO
    NINTENDO_SWITCH_JOYCON_LEFT = sdl3.SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT
    NINTENDO_SWITCH_JOYCON_RIGHT = sdl3.SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT
    NINTENDO_SWITCH_JOYCON_PAIR = sdl3.SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR
    GAMECUBE = sdl3.SDL_GAMEPAD_TYPE_GAMECUBE


class Button(enum.IntEnum):
    SOUTH = sdl3.SDL_GAMEPAD_BUTTON_SOUTH
    EAST = sdl3.SDL_GAMEPAD_BUTTON_EAST
    WEST = sdl3.SDL_GAMEPAD_BUTTON_WEST
    NORTH = sdl3.SDL_GAMEPAD_BUTTON_NORTH
    BACK = sdl3.SDL_GAMEPAD_BUTTON_BACK
    GUIDE = sdl3.SDL_GAMEPAD_BUTTON_GUIDE
    START = sdl3.SDL_GAMEPAD_BUTTON_START
    LEFT_STICK = sdl3.SDL_GAMEPAD_BUTTON_LEFT_STICK
    RIGHT_STICK = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_STICK
    LEFT_SHOULDER = sdl3.SDL_GAMEPAD_BUTTON_LEFT_SHOULDER
    RIGHT_SHOULDER = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER
    DPAD_UP = sdl3.SDL_GAMEPAD_BUTTON_DPAD_UP
    DPAD_DOWN = sdl3.SDL_GAMEPAD_BUTTON_DPAD_DOWN
    DPAD_LEFT = sdl3.SDL_GAMEPAD_BUTTON_DPAD_LEFT
    DPAD_RIGHT = sdl3.SDL_GAMEPAD_BUTTON_DPAD_RIGHT
    MISC1 = sdl3.SDL_GAMEPAD_BUTTON_MISC1
    RIGHT_PADDLE1 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_PADDLE1
    LEFT_PADDLE1 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_PADDLE1
    RIGHT_PADDLE2 = sdl3.SDL_GAMEPAD_BUTTON_RIGHT_PADDLE2
    LEFT_PADDLE2 = sdl3.SDL_GAMEPAD_BUTTON_LEFT_PADDLE2
    TOUCHPAD = sdl3.SDL_GAMEPAD_BUTTON_TOUCHPAD


class Axis(enum.IntEnum):
    LEFTX = sdl3.SDL_GAMEPAD_AXIS_LEFTX
    LEFTY = sdl3.SDL_GAMEPAD_AXIS_LEFTY
    RIGHTX = sdl3.SDL_GAMEPAD_AXIS_RIGHTX
    RIGHTY = sdl3.SDL_GAMEPAD_AXIS_RIGHTY
    LEFT_TRIGGER = sdl3.SDL_GAMEPAD_AXIS_LEFT_TRIGGER
    RIGHT_TRIGGER = sdl3.SDL_GAMEPAD_AXIS_RIGHT_TRIGGER


DEADZONE_DEFAULT = 8000


def is_playstation_type(gp_type: int) -> bool:
    return gp_type in (GamepadType.PS3, GamepadType.PS4, GamepadType.PS5)


def is_nintendo_type(gp_type: int) -> bool:
    return gp_type in (
        GamepadType.NINTENDO_SWITCH_PRO,
        GamepadType.NINTENDO_SWITCH_JOYCON_LEFT,
        GamepadType.NINTENDO_SWITCH_JOYCON_RIGHT,
        GamepadType.NINTENDO_SWITCH_JOYCON_PAIR,
    )


class ControllerManager(QObject):
    connected = Signal(str, int)
    disconnected = Signal()
    activity_changed = Signal(bool)
    button_down = Signal(int)
    button_up = Signal(int)
    axis_moved = Signal(int, int)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._controller = None
        self._instance_id = None
        self._gamepad_type = GamepadType.UNKNOWN
        self._gamepad_name = ""
        self._connected = False
        self._active = False
        self._prev_buttons = [False] * len(Button)
        self._prev_axes = [0] * len(Axis)
        self._deadzone = DEADZONE_DEFAULT

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(33)
        self._poll_timer.timeout.connect(self._poll)

        self._init_sdl()

    def _init_sdl(self) -> None:
        try:
            os.environ.setdefault("SDL_VIDEO_DRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
            if not sdl3.SDL_Init(sdl3.SDL_INIT_GAMEPAD):
                self._log_fail("SDL_Init returned False")
                return
            self._poll_timer.start()
            self._check_initial_controllers()
        except Exception as exc:
            self._log_fail(str(exc))

    def _log_fail(self, msg: str) -> None:
        try:
            from . import logger

            logger.log("debug", f"Controller init: {msg}")
        except Exception:
            pass

    def _check_initial_controllers(self) -> None:
        count = ctypes.c_int(0)
        pads = sdl3.SDL_GetGamepads(ctypes.byref(count))
        if pads and count.value > 0:
            for i in range(count.value):
                g_id = pads[i]
                if sdl3.SDL_IsGamepad(g_id):
                    self._open_controller(g_id)
                    break

    def _open_controller(self, joystick_id) -> None:
        with self._lock:
            if self._controller:
                return
            ctrl = sdl3.SDL_OpenGamepad(joystick_id)
            if not ctrl:
                return
            self._controller = ctrl
            self._instance_id = sdl3.SDL_GetGamepadID(ctrl)
            raw_name = sdl3.SDL_GetGamepadName(ctrl)
            self._gamepad_name = (
                raw_name.decode("utf-8", "replace")
                if isinstance(raw_name, bytes)
                else (raw_name or "")
            )
            raw_type = sdl3.SDL_GetGamepadType(ctrl)
            self._gamepad_type = GamepadType(raw_type)
            self._connected = True
            self._prev_buttons = [False] * len(Button)
            self._prev_axes = [0] * len(Axis)
        self.set_active(True)
        self.connected.emit(self._gamepad_name, int(self._gamepad_type))

    def _close_controller(self) -> None:
        with self._lock:
            if self._controller:
                sdl3.SDL_CloseGamepad(self._controller)
                self._controller = None
                self._instance_id = None
                self._gamepad_type = GamepadType.UNKNOWN
                self._gamepad_name = ""
                self._connected = False
        self.set_active(False)
        self.disconnected.emit()

    def _poll(self) -> None:
        sdl3.SDL_UpdateGamepads()
        event = sdl3.SDL_Event()
        while sdl3.SDL_PollEvent(ctypes.byref(event)):
            if event.type == sdl3.SDL_EVENT_GAMEPAD_ADDED:
                self._open_controller(event.gdevice.which)
            elif event.type == sdl3.SDL_EVENT_GAMEPAD_REMOVED:
                should_close = False
                with self._lock:
                    if (
                        self._instance_id is not None
                        and event.gdevice.which == self._instance_id
                    ):
                        should_close = True
                if should_close:
                    self._close_controller()
            elif event.type == sdl3.SDL_EVENT_GAMEPAD_BUTTON_DOWN:
                btn = int(event.gbutton.button)
                with self._lock:
                    if btn < len(Button):
                        self._prev_buttons[btn] = True
                self.set_active(True)
                self.button_down.emit(btn)
            elif event.type == sdl3.SDL_EVENT_GAMEPAD_BUTTON_UP:
                btn = int(event.gbutton.button)
                with self._lock:
                    if btn < len(Button):
                        self._prev_buttons[btn] = False
                self.button_up.emit(btn)

        axis_events: list[tuple[int, int]] = []
        with self._lock:
            if not self._controller:
                return
            for axis_idx in range(len(Axis)):
                val = sdl3.SDL_GetGamepadAxis(self._controller, axis_idx)
                dead = self._deadzone
                if abs(val) < dead:
                    val = 0
                if val != self._prev_axes[axis_idx]:
                    self._prev_axes[axis_idx] = val
                    axis_events.append((axis_idx, val))
        for axis_idx, val in axis_events:
            if val != 0:
                self.set_active(True)
            self.axis_moved.emit(axis_idx, val)

    def set_active(self, active: bool) -> None:
        if active != self._active:
            self._active = active
            self.activity_changed.emit(active)

    @property
    def gamepad_type(self) -> int:
        with self._lock:
            return int(self._gamepad_type)

    @property
    def gamepad_name(self) -> str:
        with self._lock:
            return self._gamepad_name

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def is_active(self) -> bool:
        return self._active

    def has_ps_labels(self) -> bool:
        with self._lock:
            if not self._controller:
                return False
            try:
                label = sdl3.SDL_GetGamepadButtonLabel(self._controller, Button.SOUTH)
                return label in (
                    sdl3.SDL_GAMEPAD_BUTTON_LABEL_CROSS,
                    sdl3.SDL_GAMEPAD_BUTTON_LABEL_CIRCLE,
                )
            except Exception:
                return False

    def set_deadzone(self, value: int) -> None:
        with self._lock:
            self._deadzone = value

    def cleanup(self) -> None:
        self._poll_timer.stop()
        self._close_controller()
        try:
            sdl3.SDL_Quit()
        except Exception:
            pass
