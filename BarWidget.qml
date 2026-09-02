import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.franzferdinan51.agent-room"

  readonly property int unread: store.unreadBoard
  readonly property bool live: store.runningAgents > 0 || store.externalWorking > 0 || store.externalWaiting > 0
  readonly property int externalAgents: store.externalTotal
  readonly property string pluginDir: {
    var s = Qt.resolvedUrl(".").toString()
    if (s.indexOf("file://") === 0) s = s.substring(7)
    while (s.length > 1 && s.charAt(s.length - 1) === "/") s = s.substring(0, s.length - 1)
    return s
  }

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
    property int externalTotal: 0
    property int externalWorking: 0
    property int externalWaiting: 0
    property string externalHeadline: ""
  }

  Process {
    id: externalStatus
    command: ["python3", root.pluginDir + "/agent-orchestr-assets/agent_ctl.py", "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var data = JSON.parse(this.text || "{}")
          var summary = data.summary || ({})
          store.externalTotal = Number(summary.total) || 0
          store.externalWorking = Number(summary.working) || 0
          store.externalWaiting = Number(summary.waiting) || 0
          store.externalHeadline = String(summary.headline || "")
        } catch (e) {
          store.externalTotal = 0
          store.externalWorking = 0
          store.externalWaiting = 0
          store.externalHeadline = ""
        }
      }
    }
  }

  Timer {
    interval: store.runningAgents > 0 || store.externalWorking > 0 || store.externalWaiting > 0 ? 2000 : 5000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!externalStatus.running) externalStatus.running = true
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
    // Use the bar's command runner, matching Omarchy's built-in bar widgets.
    // This keeps the click routed through the live shell instance after a
    // plugin rescan/reload instead of spawning a detached helper path.
    if (root.bar) root.bar.run("omarchy-shell shell toggle io.github.franzferdinan51.agent-room '{}'")
    else Quickshell.execDetached(["omarchy-shell", "shell", "toggle", "io.github.franzferdinan51.agent-room", "{}"])
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // Omarchy's built-in Agents widget uses the same robot glyph; keep this
    // mark unmistakable in the top bar.
    text: "AR"
    active: root.live || root.unread > 0
    slotSize: Style.bar.statusSlot
    tooltipText: root.unread > 0
      ? ("Agent Room · " + root.unread + " help posts" + (root.externalAgents > 0 ? " · " + root.externalAgents + " agents" : ""))
      : (root.live ? ("Agent Room · " + (root.externalAgents > 0 ? root.externalAgents + " agents active" : "agents running")) : (root.externalAgents > 0 ? "Agent Room · " + root.externalAgents + " agents" : "Agent Room"))
    onPressed: function(b) {
      if (b === Qt.RightButton) {
        if (root.bar) root.bar.run("omarchy-agent --pick")
      } else {
        root.toggleConsole()
      }
    }
  }
}
