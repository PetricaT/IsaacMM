import sys, os
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog
from PyQt6.QtGui import QIcon
import qdarkstyle


X_SIZE = 1000
Y_SIZE = 600
#
#╭─Tboi Mod Sorter────────────────────────────╮
#│                                            │
#│ "Path/To/Mods" [Please Select MODS folder] │ 
#│                                            │
#│╭─────────────────────╮    ╭──────────────╮ │
#││╭───────────────────╮│    │              │ │
#│││                   ││    │              │ │
#││╰───────────────────╯│    │              │ │
#││╭───────────────────╮│    │              │ │
#│││                   ││    │              │ │
#││╰───────────────────╯│    │              │ │
#││╭───────────────────╮│    ╰──────────────╯ │
#│││                   ││                     │
#││╰───────────────────╯│      [SAVE ORDER]   │
#││╭───────────────────╮│      [  BACKUP  ]   │
#│╰─────────────────────╯                     │
#╰────────────────────────────────────────────╯
#
class MainWindow(QWidget):
  def __init__(self):
    super().__init__()
    self.initUI()

  def initUI(self):
    self.setWindowIcon(QIcon('icon.ico'))
    self.setWindowTitle('TBOI Mod Sort')
    #                x, y, width, height
    screen = QApplication.primaryScreen()
    screenSize = screen.size()
    widthOffset = int((screenSize.width() - X_SIZE)/2)
    heightOffset = int((screenSize.height() - Y_SIZE)/2)
    self.setGeometry(widthOffset, heightOffset, X_SIZE, Y_SIZE)

    layout = self.layoutOrchestrator()    
    self.setLayout(layout)
    self.show()

  def layoutOrchestrator(self) -> QVBoxLayout:
    layout = QVBoxLayout()
    folderSelect = self.folderButton()    
    return layout

  def folderButton(self) -> QHBoxLayout:
    folderLayout = QHBoxLayout()
    self.folderLabel = QLabel('Please select the MODS folder')
    folderButton = QPushButton('Select Folder')
    folderButton.clicked.connect(self.selectFolder)
    folderLayout.addWidget(self.folderLabel)
    folderLayout.addWidget(folderButton)
    return folderLayout

  def selectFolder(self):
    folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
    if folder:
      self.folderLabel.setText(folder)
   
  def modView(self):
    pass

if __name__ == '__main__':
  app = QApplication(sys.argv)
  app.setStyleSheet(qdarkstyle.load_stylesheet())
  window = MainWindow()
  sys.exit(app.exec())