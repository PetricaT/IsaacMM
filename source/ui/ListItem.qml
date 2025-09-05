import QtQuick 6.5
import QtQuick.Controls 6.5

Item {
    width: parent ? parent.width : 200
    height: 40

    Rectangle {
        anchors.fill: parent
        color: index % 2 === 0 ? Qt.rgba(0.0,0.0,0.0,0.0) : Qt.rgba(1.0,1.0,1.0,0.1)
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 10
        anchors.rightMargin: 5
        anchors.topMargin: 0
        anchors.bottomMargin: 0

        spacing: 10

        CheckBox { id: box }
        Label { id: label; text: qsTr("Default") }
        Image {
            id: icon
            source: "file:./assets/icon.png"   // Need to figure out QRC system for better pathing
            width: 20
            height: 20
            fillMode: Image.PreserveAspectFit
        }
    }

    // Expose text property so we can set it from the delegate
    property alias text: label.text
}