import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

FloatingWindow {
  id: root
  title: "Agent Room"
  visible: true
  implicitWidth: 980
  implicitHeight: 680
  color: "#0d1018"

  property int currentTab: 0
  property string harness: "Codex"
  property string workspace: "agent-house"
  property bool compactMode: false
  property var tabs: ["Overview", "Teams", "House", "Work", "Settings"]
  property var snapshot: ({ rooms: [], board: [], work: [], mail: [], claims: [] })
  property bool settingsLoaded: false

  function loadState(raw) {
    try { snapshot = JSON.parse(raw || "{}") } catch (e) { snapshot = ({ rooms: [], board: [], work: [], mail: [], claims: [] }) }
  }

  FileView {
    id: houseFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/agent-room/house.json"
    watchChanges: true
    printErrors: false
    onLoaded: root.loadState(text())
    onFileChanged: reload()
  }

  FileView {
    id: settingsFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/agent-room/settings.json"
    printErrors: false
    onLoaded: root.loadSettings(text())
  }

  function loadSettings(raw) {
    try {
      var saved = JSON.parse(raw || "{}")
      if (saved.harness) harness = saved.harness
      if (saved.workspace) workspace = saved.workspace
      if (saved.compactMode !== undefined) compactMode = !!saved.compactMode
    } catch (e) {}
    settingsLoaded = true
  }

  function saveSettings() {
    if (settingsLoaded) settingsFile.setText(JSON.stringify({harness: harness, workspace: workspace, compactMode: compactMode}, null, 2) + "\n")
  }

  Rectangle { anchors.fill: parent; color: "#0d1018" }

  RowLayout {
    anchors.fill: parent
    anchors.margins: 24
    spacing: 22

    Rectangle {
      Layout.fillHeight: true; Layout.preferredWidth: 190; radius: 18; color: "#141a27"
      ColumnLayout {
        anchors.fill: parent; anchors.margins: 14; spacing: 8
        RowLayout {
          Layout.fillWidth: true; Layout.bottomMargin: 18
          Rectangle { width: 38; height: 38; radius: 11; color: "#7c5cff"
            Text { anchors.centerIn: parent; text: "⌁"; color: "white"; font.pixelSize: 25; font.bold: true }
          }
          ColumnLayout { spacing: 0
            Text { text: "AGENT"; color: "#8e9ab5"; font.pixelSize: 10; font.bold: true; font.letterSpacing: 1.5 }
            Text { text: "ROOM"; color: "#f3f6ff"; font.pixelSize: 18; font.bold: true }
          }
        }
        Repeater {
          model: root.tabs
          delegate: Rectangle {
            Layout.fillWidth: true; height: 42; radius: 10
            color: root.currentTab === index ? "#252d43" : "transparent"
            RowLayout { anchors.fill: parent; anchors.leftMargin: 12; spacing: 12
              Text { text: ["◈", "◉", "✦", "▤", "⚙"][index]; color: root.currentTab === index ? "#a8e6ff" : "#8792a8"; font.pixelSize: 17 }
              Text { text: modelData; color: root.currentTab === index ? "#f2f5ff" : "#a1abc0"; font.pixelSize: 14; font.bold: root.currentTab === index }
            }
            MouseArea { anchors.fill: parent; onClicked: root.currentTab = index }
          }
        }
        Item { Layout.fillHeight: true }
        Text { text: "LOCAL • PRIVATE"; color: "#64708a"; font.pixelSize: 10; font.letterSpacing: 1 }
      }
    }

    ColumnLayout {
      Layout.fillWidth: true; Layout.fillHeight: true; spacing: 18
      RowLayout { Layout.fillWidth: true
        ColumnLayout { Layout.fillWidth: true; spacing: 3
          Text { text: root.tabs[root.currentTab]; color: "#f4f7ff"; font.pixelSize: 28; font.bold: true }
          Text { text: root.currentTab === 4 ? "Tune your room without leaving the shell." : "Your local command center for cooperative agents."; color: "#8995ae"; font.pixelSize: 13 }
        }
        Rectangle { width: 108; height: 34; radius: 9; color: "#182132"
          Text { anchors.centerIn: parent; text: "●  LOCAL"; color: "#8de5bb"; font.pixelSize: 11; font.bold: true }
        }
      }

      StackLayout { Layout.fillWidth: true; Layout.fillHeight: true; currentIndex: root.currentTab
        Item { // Overview
          ColumnLayout { anchors.fill: parent; spacing: 14
            RowLayout { Layout.fillWidth: true; spacing: 14
              Repeater { model: [{n: "Rooms", v: root.snapshot.rooms ? root.snapshot.rooms.length : 0}, {n: "Open help", v: root.snapshot.board ? root.snapshot.board.length : 0}, {n: "Work items", v: root.snapshot.work ? root.snapshot.work.length : 0}]
                delegate: Rectangle { Layout.fillWidth: true; height: 105; radius: 14; color: "#141a27"
                  Column { anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 7
                    Text { text: modelData.n; color: "#8792a8"; font.pixelSize: 12 }
                    Text { text: modelData.v; color: "#f3f6ff"; font.pixelSize: 28; font.bold: true }
                  }
                }
              }
            }
            Rectangle { Layout.fillWidth: true; Layout.fillHeight: true; radius: 14; color: "#141a27"
              ColumnLayout { anchors.fill: parent; anchors.margins: 20; spacing: 12
                Text { text: "Room pulse"; color: "#eaf0ff"; font.pixelSize: 17; font.bold: true }
                Text { visible: !root.snapshot.rooms || root.snapshot.rooms.length === 0; text: "No rooms yet. Create one with agent-room and it will appear here."; color: "#8995ae"; font.pixelSize: 14 }
                Repeater { model: root.snapshot.rooms || []; delegate: Rectangle { Layout.fillWidth: true; height: 54; radius: 9; color: "#1b2232"
                    RowLayout { anchors.fill: parent; anchors.margins: 12; Text { text: modelData.name || "Room"; color: "#f2f5ff"; font.bold: true; Layout.fillWidth: true }; Text { text: modelData.status || "ready"; color: "#8de5bb"; font.pixelSize: 12 } }
                  } }
              }
            }
          }
        }
        Item { Text { anchors.centerIn: parent; text: "Teams and agent conversations will appear here."; color: "#8995ae"; font.pixelSize: 15 } }
        Item { Text { anchors.centerIn: parent; text: "House health and help requests will appear here."; color: "#8995ae"; font.pixelSize: 15 } }
        Item { Text { anchors.centerIn: parent; text: "Work capsules and file claims will appear here."; color: "#8995ae"; font.pixelSize: 15 } }
        Item { // Settings
          Flickable { anchors.fill: parent; contentHeight: settingsColumn.height; clip: true
            ColumnLayout { id: settingsColumn; width: parent.width; spacing: 12
              Text { text: "General"; color: "#a8e6ff"; font.pixelSize: 12; font.bold: true; font.letterSpacing: 1 }
              Rectangle { Layout.fillWidth: true; height: 72; radius: 12; color: "#141a27"
                RowLayout { anchors.fill: parent; anchors.margins: 16; ColumnLayout { Layout.fillWidth: true; spacing: 3; Text { text: "Default harness"; color: "#eef2ff"; font.pixelSize: 14 }; Text { text: "Used when a new room seat is created"; color: "#7e8aa3"; font.pixelSize: 12 } }; ComboBox { model: ["Codex", "Claude Code", "Hermes Agent", "Grok Build", "Gemini", "Copilot"]; currentIndex: Math.max(0, model.indexOf(root.harness)); onActivated: { root.harness = currentText; root.saveSettings() } } }
              }
              Rectangle { Layout.fillWidth: true; height: 72; radius: 12; color: "#141a27"
                RowLayout { anchors.fill: parent; anchors.margins: 16; ColumnLayout { Layout.fillWidth: true; spacing: 3; Text { text: "Workspace"; color: "#eef2ff"; font.pixelSize: 14 }; Text { text: "Hyprland workspace used by agent seats"; color: "#7e8aa3"; font.pixelSize: 12 } }; TextField { text: root.workspace; placeholderText: "agent-house"; onTextChanged: { root.workspace = text; root.saveSettings() }; Layout.preferredWidth: 150 } }
              }
              Text { text: "Appearance"; color: "#a8e6ff"; font.pixelSize: 12; font.bold: true; font.letterSpacing: 1; Layout.topMargin: 12 }
              Rectangle { Layout.fillWidth: true; height: 72; radius: 12; color: "#141a27"
                RowLayout { anchors.fill: parent; anchors.margins: 16; ColumnLayout { Layout.fillWidth: true; spacing: 3; Text { text: "Compact navigation"; color: "#eef2ff"; font.pixelSize: 14 }; Text { text: "Reduce sidebar spacing for smaller screens"; color: "#7e8aa3"; font.pixelSize: 12 } }; Switch { checked: root.compactMode; onToggled: { root.compactMode = checked; root.saveSettings() } } }
              }
              Text { text: "State is stored locally in ~/.local/state/omarchy/agent-room/"; color: "#65718a"; font.pixelSize: 12; Layout.topMargin: 10 }
            }
          }
        }
      }
    }
  }
}
