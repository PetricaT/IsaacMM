import QtQuick 6.5
import QtQuick.Controls 6.5

ApplicationWindow {
    visible: true
    width: 600
    height: 400
    title: "Isaac Mod Manager"

    Row {
        anchors.fill: parent
        spacing: 10

        // The list with custom items
        ListView {
            id: listView
            width: parent.width * 0.7
            height: parent.height

            model: ListModel {
                ListElement { text: "Mod 1" }
                ListElement { text: "Mod 2" }
                ListElement { text: "Mod 3" }
            }

            delegate: ListItem {
                text: model.text
            }

            interactive: true
        }

        // Buttons on the side
        Column {
            spacing: 10
            Button {
                text: "Add"
                onClicked: listView.model.append({ "text": "More mods" })
            }
            Button {
                text: "Remove"
                onClicked: if (listView.currentIndex >= 0)
                              listView.model.remove(listView.currentIndex)
            }
        }
    }
}
