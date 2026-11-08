/* ENVY BLACK VEIL — Calamares install slideshow (API 2). */
import QtQuick 2.15
import calamares.slideshow 1.0

Presentation {
    id: presentation

    property int loadingProgress: 0

    function onActivate() { presentation.startAutoAdvance(12000); }
    function onLeave() { presentation.stopAutoAdvance(); }

    Timer {
        id: advanceTimer
        interval: 12000
        running: false
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }
    function startAutoAdvance(ms) { advanceTimer.interval = ms; advanceTimer.running = true; }
    function stopAutoAdvance() { advanceTimer.running = false; }

    Slide {
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            color: "#050713"
            Column {
                anchors.centerIn: parent
                spacing: 14
                Text { text: "ENVY BLACK VEIL"; color: "#f2f4ff"; font.pixelSize: 44; font.bold: true
                       anchors.horizontalCenter: parent.horizontalCenter }
                Text { text: "Just the OS. Your tools come next."; color: "#35e8ff"; font.pixelSize: 18
                       anchors.horizontalCenter: parent.horizontalCenter }
            }
        }
    }

    Slide {
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            color: "#050713"
            Column {
                anchors.centerIn: parent
                spacing: 10
                width: parent.width * 0.7
                Text { text: "Add any ENVY tool, any time"; color: "#ff3db4"; font.pixelSize: 30; font.bold: true
                       anchors.horizontalCenter: parent.horizontalCenter }
                Text { text: "After setup, open a terminal and run:\n\n    envy-tools install vault veil hypothesis\n\nEverything installs into one isolated environment and lands in your menu."
                       color: "#b9c3df"; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                       width: parent.width; anchors.horizontalCenter: parent.horizontalCenter }
            }
        }
    }

    Slide {
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            color: "#050713"
            Column {
                anchors.centerIn: parent
                spacing: 10
                width: parent.width * 0.7
                Text { text: "Encrypted and offline by design"; color: "#ac8cff"; font.pixelSize: 30; font.bold: true
                       anchors.horizontalCenter: parent.horizontalCenter }
                Text { text: "SELinux enforcing, the firewall on, nothing listening. Every ENVY tool works with no network and no account — nothing leaves this machine."
                       color: "#b9c3df"; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                       width: parent.width; anchors.horizontalCenter: parent.horizontalCenter }
            }
        }
    }
}
