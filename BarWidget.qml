import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.franzferdinan51.agent-room"

  readonly property int unread: store.unreadBoard
  readonly property bool live: store.runningAgents > 0

  FileView {
    id: storeFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/agent-room/house.json"
    watchChanges: true
    printErrors: false
    onLoaded: root.parseStore(text())
    onFileChanged: reload()
  }

  QtObject {
    id: store
    property int unreadBoard: 0
    property int runningAgents: 0
    property int teams: 0
  }

  function parseStore(raw) {
    try {
      var data = JSON.parse(raw || "{}")
      var board = data.board || []
      var n = 0
      for (var i = 0; i < board.length; i++)
        if (board[i].status === "open") n++
      store.unreadBoard = n
      var running = 0
      var rooms = data.rooms || []
      store.teams = rooms.length
      for (var r = 0; r < rooms.length; r++) {
        var roles = rooms[r].roles || []
        for (var k = 0; k < roles.length; k++)
          if (roles[k].status === "running") running++
      }
      store.runningAgents = running
    } catch (e) {
      store.unreadBoard = 0
      store.runningAgents = 0
    }
  }

  function toggleConsole() {
    Quickshell.execDetached(["omarchy-shell", "shell", "toggle", "io.github.franzferdinan51.agent-room", "{}"])
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "⌁"
    active: root.live || root.unread > 0
    slotSize: Style.bar.statusSlot
    tooltipText: root.unread > 0
      ? ("Agent Room · " + root.unread + " help posts")
      : (root.live ? "Agent Room · agents running" : "Agent Room")
    onPressed: function(b) {
      if (b === Qt.RightButton) {
        if (root.bar) root.bar.run("omarchy-agent --pick")
      } else {
        root.toggleConsole()
      }
    }
  }
}
