// ENVY BLACK VEIL — SDDM greeter. QtQuick plus SDDM's own components (TextBox,
// PasswordBox, ComboBox, Button), so it runs on a stock SDDM with the Qt6 greeter.
// Palette comes from theme.conf (config.*), with ENVY fallbacks.
import QtQuick 2.15
import SddmComponents 2.0

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: config.color !== "" ? config.color : "#050713"

    property string cPink: config.pink !== "" ? config.pink : "#ff3db4"
    property string cCyan: config.cyan !== "" ? config.cyan : "#35e8ff"
    property string cInk: config.ink !== "" ? config.ink : "#f2f4ff"
    property string cMuted: config.muted !== "" ? config.muted : "#b9c3df"
    property string cPanel: config.panel !== "" ? config.panel : "#0a0e22"
    property string cLine: config.line !== "" ? config.line : "#1f2547"

    TextConstants { id: textConstants }

    // SDDM's user model: Qt.UserRole + 1 is the user name role.
    function userName(i) { return userModel.data(userModel.index(i, 0), Qt.UserRole + 1) }
    function doLogin() { sddm.login(userName(user.index), password.text, session.index) }

    Connections {
        target: sddm
        function onLoginSucceeded() { }
        function onLoginFailed() {
            message.text = "Login failed — check the passphrase."
            password.text = ""
            password.forceActiveFocus()
        }
    }

    Image {
        anchors.fill: parent
        source: config.background
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: config.type === "image"
    }

    // Soft neon glows.
    Rectangle {
        anchors.centerIn: parent
        anchors.horizontalCenterOffset: -360
        width: 620; height: 620; radius: 310; opacity: 0.18
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.cPink }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: 26
        width: 420

        // Wordmark.
        Column {
            spacing: 2
            anchors.horizontalCenter: parent.horizontalCenter
            Text {
                text: "ENVY"
                color: root.cInk
                font.pixelSize: 64; font.bold: true; font.letterSpacing: 3
                anchors.horizontalCenter: parent.horizontalCenter
            }
            Text {
                text: "BLACK VEIL"
                color: root.cCyan
                font.pixelSize: 20; font.letterSpacing: 8
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }

        // Login panel.
        Rectangle {
            width: parent.width; height: 206; radius: 16
            color: root.cPanel
            border.color: root.cLine; border.width: 1

            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14

                ComboBox {
                    id: user
                    width: parent.width; height: 40
                    model: userModel
                    index: userModel.lastIndex
                    color: "#121735"; textColor: root.cInk
                    borderColor: root.cLine; focusColor: root.cCyan; hoverColor: "#2a3470"
                    menuColor: "#0f1330"; arrowColor: "#121735"; arrowIcon: Qt.resolvedUrl("chevron.svg")
                }

                PasswordBox {
                    id: password
                    width: parent.width; height: 40
                    color: "#121735"; textColor: root.cInk
                    borderColor: root.cLine; focusColor: root.cPink; hoverColor: root.cCyan
                    focus: true
                    Keys.onPressed: function (event) {
                        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            root.doLogin()
                            event.accepted = true
                        }
                    }
                    KeyNavigation.backtab: user; KeyNavigation.tab: loginButton
                }

                Button {
                    id: loginButton
                    width: parent.width; height: 42
                    text: "Unlock"
                    color: root.cPink; activeColor: root.cCyan; pressedColor: root.cCyan
                    textColor: "#050713"
                    onClicked: root.doLogin()
                    KeyNavigation.backtab: password; KeyNavigation.tab: session
                }
            }
        }

        Text {
            id: message
            anchors.horizontalCenter: parent.horizontalCenter
            color: root.cMuted
            font.pixelSize: 12
            text: "Encrypted desktop · nothing leaves this machine"
        }

        // Session + power, understated.
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 18
            ComboBox {
                id: session
                width: 190; height: 30
                model: sessionModel
                index: sessionModel.lastIndex
                color: "#121735"; textColor: root.cMuted
                borderColor: root.cLine; focusColor: root.cCyan; hoverColor: "#2a3470"
                menuColor: "#0f1330"; arrowColor: "#121735"; arrowIcon: Qt.resolvedUrl("chevron.svg")
            }
            Button {
                height: 30; width: 90; text: "Restart"
                color: "#121735"; textColor: root.cMuted; activeColor: root.cLine
                onClicked: sddm.reboot()
            }
            Button {
                height: 30; width: 90; text: "Shut down"
                color: "#121735"; textColor: root.cMuted; activeColor: root.cLine
                onClicked: sddm.powerOff()
            }
        }
    }

    Component.onCompleted: password.forceActiveFocus()
}
