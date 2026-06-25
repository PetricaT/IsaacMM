import os
import sys

sys.path.insert(0, os.path.abspath('..'))

# Mock PySide6 and toml for autodoc so doc builds don't need Qt installed.
# toml is mocked as a fallback in case it's not installed on RTD.
import unittest.mock as mock

class _ItemDataRole:
    UserRole = 256

class _AlignmentFlag:
    AlignLeft = 1
    AlignVCenter = 4
    AlignCenter = 5

class _CheckState:
    Unchecked = 0
    Checked = 2

class _AspectRatioMode:
    KeepAspectRatio = 1

class _TransformationMode:
    SmoothTransformation = 1
    FastTransformation = 0

class _Orientation:
    Horizontal = 1

class _DropAction:
    MoveAction = 2

class _ConnectionType:
    DirectConnection = 1

class _FocusPolicy:
    NoFocus = 0

class _ScrollBarPolicy:
    ScrollBarAsNeeded = 0

class _CursorShape:
    PointingHandCursor = 2

class _KeyboardModifier:
    ControlModifier = 67108864

class _ContextMenuPolicy:
    CustomContextMenu = 3

class _Qt:
    ItemDataRole = _ItemDataRole()
    AlignmentFlag = _AlignmentFlag()
    CheckState = _CheckState()
    AspectRatioMode = _AspectRatioMode()
    TransformationMode = _TransformationMode()
    Orientation = _Orientation()
    DropAction = _DropAction()
    ConnectionType = _ConnectionType()
    FocusPolicy = _FocusPolicy()
    ScrollBarPolicy = _ScrollBarPolicy()
    CursorShape = _CursorShape()
    KeyboardModifier = _KeyboardModifier()
    ContextMenuPolicy = _ContextMenuPolicy()

_MOCK_MODULES = [
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvgWidgets',
    'toml',
]
for mod_name in _MOCK_MODULES:
    sys.modules[mod_name] = mock.MagicMock()

sys.modules['PySide6.QtCore'].Qt = _Qt()
sys.modules['PySide6'].Qt = _Qt()

project = 'IsaacMM'
copyright = '2026, PetricaT'
author = 'PetricaT'
release = '0.5.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.autosummary',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
try:
    import sphinx_rtd_theme
except ImportError:
    html_theme = 'alabaster'

html_static_path = ['_static']
