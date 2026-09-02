import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Item {
  id: root
  width: 980
  height: 860

  property var shell: null
  property var manifest: null
  property bool closingFromHost: false
  property string tab: "teams"
  property int selectedRoom: 0
  property string editRoomId: ""
  property string editRoomName: ""
  property string editRoomGoal: ""
  property string editRoomWorkspace: ""
  property bool deleteArmed: false
  property string roomFilter: ""
  property string pendingMaintenance: ""
  property var house: ({})
  property string formName: ""
  property string formGoal: ""
  property string formWorkspace: ""
  property string formCwd: Quickshell.env("HOME") + "/Work"
  property string formProgram: ""
  property bool formCoordinator: true
  property bool formBuilder: true
  property bool formReviewer: true
  property bool formJudge: true
  property bool formCreative: true
  property string formHCoordinator: "multi-agent-cli"
  property string formHBuilder: "multi-agent-cli"
  property string formHReviewer: "multi-agent-cli"
  property string formHJudge: "multi-agent-cli"
  property string formHCreative: "multi-agent-cli"
  property string formTCoordinator: "tui"
  property string formTBuilder: "tui"
  property string formTReviewer: "tui"
  property string formTJudge: "acp"
  property string formTCreative: "tui"
  property string lastError: ""
  property bool houseLoaded: false
  property string composeText: ""
  property string contextDraft: ""
  property string planDraft: ""
  property string workTitleDraft: ""
  property string workBriefDraft: ""
  property string commandFilter: ""
  property bool startAfterCreate: false
  property string settingsDefaultHarness: "multi-agent-cli"
  property string settingsDefaultModel: ""
  property string settingsDefaultTransport: "tui"
  property bool settingsMixed: true
  property bool settingsAcp: true
  property bool settingsHermes: true
  property string settingsWorkspace: "current"
  property bool settingsHydrated: false
  property var grokModelOptions: []
  property string telegramToken: ""
  property string telegramTeam: ""
  property bool telegramAutoApprove: false

  onTabChanged: {
    if (scrollArea && scrollArea.contentItem) scrollArea.contentItem.contentY = 0
    // Context, Plan, Work, and Teams all read the same file-backed house.
    // Refresh as soon as the user opens a tab so agent writes are visible
    // immediately instead of waiting for the background polling interval.
    root.reloadHouse()
  }

  readonly property color foreground: Color.foreground
  readonly property color background: Color.background
  readonly property color accent: Color.accent
  readonly property color urgent: Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color card: Color.popups.background
  readonly property string fontFamily: Style.font.family
  readonly property string pluginDir: {
    var s = Qt.resolvedUrl(".").toString()
    if (s.indexOf("file://") === 0) s = s.substring(7)
    while (s.length > 1 && s.charAt(s.length - 1) === "/")
      s = s.substring(0, s.length - 1)
    return s
  }
  readonly property var rooms: house.rooms || []
  readonly property var filteredRooms: {
    var query = root.roomFilter.trim().toLowerCase()
    var out = []
    for (var i = 0; i < root.rooms.length; i++) {
      var r = root.rooms[i]
      var haystack = ((r.name || "") + " " + (r.goal || "") + " " + (r.status || "")).toLowerCase()
      if (!query || haystack.indexOf(query) >= 0) out.push({ room: r, index: i })
    }
    return out
  }
  readonly property var stats: {
    var s = house.stats || ({})
    if (s.teams !== undefined) return s
    var mail = house.mail || []
    var work = house.work || []
    var board = house.board || []
    var running = 0
    var rs = house.rooms || []
    for (var i = 0; i < rs.length; i++) {
      var roles = rs[i].roles || []
      for (var k = 0; k < roles.length; k++)
        if (roles[k].status === "running") running++
    }
    return {
      teams: rs.length,
      running: running,
      messages: mail.length,
      open_board: board.length,
      active_work: work.length,
      blocked_work: 0,
      claims: (house.claims || []).length,
      cmds: (house.cmds || []).length,
      plan: (house.plan || []).length,
      health: (house.health || []).length,
      context: (house.context || []).length
    }
  }
  readonly property var meta: house.meta || ({})
  readonly property var hermes: house.hermes || ({})
  readonly property var telegramStatus: house.telegram_status || ({ status: "disconnected", polling: false, configured: false })
  readonly property var telegramState: house.telegram || ({ pending: [], approved: [] })
  readonly property var telegramTeamOptions: {
    var out = [{ value: "", label: "First team" }]
    for (var i = 0; i < root.rooms.length; i++) out.push({ value: root.rooms[i].id, label: root.rooms[i].name || root.rooms[i].id })
    return out
  }
  readonly property var harnessOptions: {
    var hs = house.harnesses || []
    var out = []
    for (var i = 0; i < hs.length; i++) {
      var mark = hs[i].installed ? "" : "  · missing"
      var acp = hs[i].acp_ready ? "  · ACP" : ""
      out.push({ value: hs[i].id, label: (hs[i].label || hs[i].id) + acp + mark })
    }
    if (out.length === 0) {
      out = [
        { value: "multi-agent-cli", label: "MultiAgentCli (LM Studio)" },
        { value: "grok", label: "Grok Build" },
        { value: "grok-local", label: "Grok Local" },
        { value: "codex", label: "Codex" },
        { value: "claude", label: "Claude Code" },
        { value: "hermes", label: "Hermes" }
      ]
    }
    return out
  }
  readonly property var transportOptions: [
    { value: "tui", label: "TUI terminal" },
    { value: "acp", label: "ACP stdio" }
  ]
  function modelOptionsFor(harness) {
    if ((harness === "grok" || harness === "grok-local") && root.grokModelOptions.length > 0)
      return root.grokModelOptions
    var options = {
      grok: [{ value: "", label: "Auto (account default)" }, { value: "grok-4.1", label: "Grok 4.1" }, { value: "grok-4.1-mini", label: "Grok 4.1 Mini" }],
      "grok-local": [{ value: "", label: "Auto (local default)" }],
      codex: [{ value: "", label: "Auto (account default)" }, { value: "gpt-5.2-codex", label: "GPT-5.2 Codex" }, { value: "gpt-5.1-codex-mini", label: "GPT-5.1 Codex Mini" }],
      claude: [{ value: "", label: "Auto (account default)" }, { value: "claude-sonnet-4-5", label: "Claude Sonnet 4.5" }, { value: "claude-opus-4-1", label: "Claude Opus 4.1" }],
      hermes: [{ value: "", label: "Config default" }, { value: "qwen3-coder", label: "Qwen3 Coder" }, { value: "deepseek-v3", label: "DeepSeek V3" }],
      gemini: [{ value: "", label: "Auto (account default)" }, { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" }, { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" }],
      opencode: [{ value: "", label: "Auto (provider default)" }, { value: "anthropic/claude-sonnet-4-5", label: "Claude Sonnet 4.5" }, { value: "openai/gpt-5", label: "GPT-5" }]
    }
    var out = (options[harness] || [{ value: "", label: "Auto (harness default)" }]).slice()
    var seen = {}
    for (var i = 0; i < out.length; i++) seen[out[i].value] = true
    // Expose discovered local models to every harness selector so custom/local
    // models are not hidden by fallback lists. The selected harness decides
    // how the model is run.
    for (var k = 0; k < root.grokModelOptions.length; k++) {
      var discovered = root.grokModelOptions[k]
      if (!discovered.value || seen[discovered.value]) continue
      out.push({ value: discovered.value, label: "Grok / LM Studio · " + discovered.label })
      seen[discovered.value] = true
    }
    return out
  }
  function loadGrokModels(raw) {
    try {
      var parsed = JSON.parse(raw || "{}")
      if (parsed.models && parsed.models.length > 0) root.grokModelOptions = parsed.models
    } catch (e) {}
  }
  readonly property var modelOptions: modelOptionsFor(root.settingsDefaultHarness)
  readonly property var room: rooms.length > 0 ? rooms[Math.min(selectedRoom, rooms.length - 1)] : null
  readonly property var roomMail: {
    var out = []
    var mail = house.mail || []
    if (!room) return out
    for (var i = 0; i < mail.length; i++)
      if (mail[i].room_id === room.id) out.push(mail[i])
    return out
  }
  readonly property var roomWork: {
    var out = []
    var work = house.work || []
    if (!room) return out
    for (var i = 0; i < work.length; i++)
      if (work[i].room_id === room.id) out.push(work[i])
    return out
  }
  readonly property var roomBoard: {
    var out = []
    var board = house.board || []
    if (!room) return out
    for (var i = 0; i < board.length; i++)
      if (board[i].room_id === room.id) out.push(board[i])
    return out
  }
  readonly property int doneRoles: {
    if (!room) return 0
    var n = 0
    var roles = room.roles || []
    for (var i = 0; i < roles.length; i++)
      if (roles[i].status === "completed" || roles[i].status === "complete") n++
    return n
  }

  function open(payloadJson) {
    closingFromHost = false
    window.visible = true
    reloadHouse()
    Qt.callLater(function() { if (keyCatcher) keyCatcher.forceActiveFocus() })
  }

  function close() {
    closingFromHost = true
    window.visible = false
    closingFromHost = false
  }

  function requestClose() {
    if (shell && typeof shell.hide === "function")
      shell.hide("io.github.franzferdinan51.agent-room")
    else window.visible = false
  }

  function reloadHouse() {
    houseFile.reload()
  }

  function refreshModels() {
    modelDiscovery.running = false
    modelDiscovery.running = true
  }

  function parseHouse(raw) {
    try {
      house = JSON.parse(raw || "{}")
      houseLoaded = true
      lastError = ""
      var selectedIndex = -1
      for (var i = 0; i < root.rooms.length; i++) {
        if (root.rooms[i].id === root.editRoomId) selectedIndex = i
      }
      if (root.editRoomId && selectedIndex < 0) {
        editRoomId = ""
        editRoomName = ""
        editRoomGoal = ""
        deleteArmed = false
      } else if (selectedIndex >= 0) {
        selectedRoom = selectedIndex
      } else if (root.rooms.length === 0) {
        selectedRoom = 0
      } else if (selectedRoom >= root.rooms.length) {
        selectedRoom = root.rooms.length - 1
      }
      var s = house.settings || {}
      if (root.settingsHydrated) return
      root.settingsHydrated = true
      if (s.default_harness) settingsDefaultHarness = s.default_harness
      if (s.default_model !== undefined) settingsDefaultModel = s.default_model
      if (s.default_transport) settingsDefaultTransport = s.default_transport
      if (s.workspace) settingsWorkspace = s.workspace
      if (s.mixed_harness !== undefined) settingsMixed = !!s.mixed_harness
      if (s.acp_enabled !== undefined) settingsAcp = !!s.acp_enabled
      if (s.hermes_enabled !== undefined) settingsHermes = !!s.hermes_enabled
      if (s.telegram_team !== undefined) telegramTeam = s.telegram_team
      if (s.telegram_auto_approve !== undefined) telegramAutoApprove = !!s.telegram_auto_approve
      var rh = s.role_harness || {}
      if (rh.coordinator) formHCoordinator = rh.coordinator
      if (rh.builder) formHBuilder = rh.builder
      if (rh.reviewer) formHReviewer = rh.reviewer
      if (rh.judge) formHJudge = rh.judge
      if (rh["creative-director"]) formHCreative = rh["creative-director"]
      var rt = s.role_transport || {}
      if (rt.coordinator) formTCoordinator = rt.coordinator
      if (rt.builder) formTBuilder = rt.builder
      if (rt.reviewer) formTReviewer = rt.reviewer
      if (rt.judge) formTJudge = rt.judge
      if (rt["creative-director"]) formTCreative = rt["creative-director"]
    } catch (e) {
      houseLoaded = true
      lastError = "Could not read house state"
    }
  }

  function runCli(args, env) {
    if (cli.running) return
    lastError = ""
    cli.environment = env || ({})
    cli.command = [pluginDir + "/bin/agent-room"].concat(args)
    cli.running = true
  }

  function createRoom() {
    var roles = []
    if (formCoordinator) roles.push("coordinator")
    if (formBuilder) roles.push("builder")
    if (formReviewer) roles.push("reviewer")
    if (formJudge) roles.push("judge")
    if (formCreative) roles.push("creative-director")
    if (!formName.trim() || !formGoal.trim()) {
      lastError = "Name and goal are required"
      return
    }
    var args = ["create-room", "--name", formName.trim(), "--goal", formGoal.trim(), "--cwd", formCwd.trim() || (Quickshell.env("HOME") + "/Work"), "--roles", roles.join(",")]
    if (formWorkspace.trim()) args = args.concat(["--workspace", formWorkspace.trim()])
    if (formProgram.trim()) args = args.concat(["--harness", formProgram.trim()])
    if (formCoordinator) args = args.concat(["--seat", "coordinator=" + formHCoordinator + ":" + formTCoordinator])
    if (formBuilder) args = args.concat(["--seat", "builder=" + formHBuilder + ":" + formTBuilder])
    if (formReviewer) args = args.concat(["--seat", "reviewer=" + formHReviewer + ":" + formTReviewer])
    if (formJudge) args = args.concat(["--seat", "judge=" + formHJudge + ":" + formTJudge])
    if (formCreative) args = args.concat(["--seat", "creative-director=" + formHCreative + ":" + formTCreative])
    tab = "house"
    runCli(args)
  }

  function selectRoomForEdit(index) {
    var selected = root.rooms[index]
    if (!selected) return
    selectedRoom = index
    editRoomId = selected.id || ""
    editRoomName = selected.name || ""
    editRoomGoal = selected.goal || ""
    editRoomWorkspace = selected.workspace || root.settingsWorkspace || "current"
    deleteArmed = false
  }

  function editSelectedRoom() {
    if (!editRoomId || !editRoomName.trim() || !editRoomGoal.trim()) {
      lastError = "Team name and goal are required"
      return
    }
    runCli(["update-room", editRoomId, "--name", editRoomName.trim(), "--goal", editRoomGoal.trim(), "--workspace", editRoomWorkspace.trim()])
  }

  function editCurrentRoom() {
    if (!root.room) return
    root.selectRoomForEdit(root.selectedRoom)
    root.tab = "house"
  }

  function setSeatModel(roleId, model) {
    if (!root.room) return
    root.runCli(["set-seat", root.room.id, roleId, "--model", model || ""])
  }

  function deleteSelectedRoom() {
    if (!editRoomId) return
    if (!deleteArmed) {
      deleteArmed = true
      return
    }
    runCli(["delete-room", editRoomId])
    selectedRoom = 0
    editRoomId = ""
    editRoomName = ""
    editRoomGoal = ""
    editRoomWorkspace = ""
    deleteArmed = false
  }

  function runMaintenance(action) {
    if (pendingMaintenance !== action) {
      pendingMaintenance = action
      return
    }
    pendingMaintenance = ""
    runCli([action])
  }

  function saveSettings() {
    var patch = {
      default_harness: settingsDefaultHarness,
      default_model: settingsDefaultModel,
      default_transport: settingsDefaultTransport,
      mixed_harness: settingsMixed,
      acp_enabled: settingsAcp,
      hermes_enabled: settingsHermes,
      workspace: settingsWorkspace,
      telegram_team: telegramTeam,
      telegram_auto_approve: telegramAutoApprove,
      role_harness: {
        coordinator: formHCoordinator,
        builder: formHBuilder,
        reviewer: formHReviewer,
        judge: formHJudge,
        "creative-director": formHCreative
      },
      role_transport: {
        coordinator: formTCoordinator,
        builder: formTBuilder,
        reviewer: formTReviewer,
        judge: formTJudge,
        "creative-director": formTCreative
      }
    }
    runCli(["set-settings", "--json", JSON.stringify(patch)])
  }

  function telegramAction(action) {
    if (action === "set-token") {
      if (!telegramToken.trim()) { lastError = "Enter the bot token first"; return }
      runCli(["telegram-set-token"], { AGENT_ROOM_TELEGRAM_TOKEN: telegramToken.trim() })
      telegramToken = ""
      return
    }
    runCli(["telegram-" + action])
  }

  function telegramApprove(chatId) { runCli(["telegram-approve", String(chatId)]) }
  function telegramDeny(chatId) { runCli(["telegram-deny", String(chatId)]) }

  function switchSeat(roleId, harness, transport) {
    if (!room) return
    var args = ["set-seat", room.id, roleId, "--restart"]
    if (harness) args = args.concat(["--harness", harness])
    if (transport) args = args.concat(["--transport", transport])
    runCli(args)
  }

  function startSelected() {
    if (!room) return
    runCli(["start-room", room.id])
  }

  function stopSelected() {
    if (!room) return
    runCli(["stop-room", room.id])
  }

  function hideMonitor() {
    if (!room) return
    runCli(["set-monitor", room.id, "--hidden", room.monitor_hidden ? "false" : "true"])
  }

  function reviewRoom() {
    var args = ["review"]
    if (room) args = args.concat(["--room", room.id])
    runCli(args)
  }

  function sendCompose() {
    if (!room || !composeText.trim()) return
    runCli(["send", "--room", room.id, "--from", "operator", "--to", "*", "--subject", "Operator", "--body", composeText.trim()])
    composeText = ""
  }

  function addContext() {
    if (!room || !contextDraft.trim()) return
    runCli(["context-write", "--room", room.id, "--author", "operator", "--text", contextDraft.trim()])
    contextDraft = ""
  }

  function addPlan() {
    if (!room || !planDraft.trim()) return
    runCli(["plan-add", "--room", room.id, "--author", "operator", "--text", planDraft.trim()])
    planDraft = ""
  }

  function createWork() {
    if (!room || !workTitleDraft.trim() || !workBriefDraft.trim()) return
    runCli(["create-work", "--room", room.id, "--title", workTitleDraft.trim(), "--brief", workBriefDraft.trim(), "--owner", "operator"])
    workTitleDraft = ""
    workBriefDraft = ""
  }

  FileView {
    id: houseFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/agent-room/house.json"
    watchChanges: true
    printErrors: false
    onLoaded: root.parseHouse(text())
    onLoadFailed: { root.lastError = "House state is unavailable; retrying…"; root.runCli(["init"]) }
    onFileChanged: reload()
  }

  Process {
    id: cli
    stdout: StdioCollector {
      onStreamFinished: {
        root.reloadHouse()
        var text = this.text || ""
        if (text.indexOf("\"id\"") >= 0) {
          try {
            var created = JSON.parse(text)
            if (created && created.id) {
              for (var i = 0; i < root.rooms.length; i++)
                if (root.rooms[i].id === created.id) root.selectedRoom = i
              if (root.startAfterCreate) {
                root.startAfterCreate = false
                root.runCli(["start-room", created.id])
              }
            }
          } catch (e) {}
        }
      }
    }
    stderr: StdioCollector {
      onStreamFinished: {
        if (this.text && this.text.trim()) root.lastError = this.text.trim()
      }
    }
  }

  Process {
    id: modelDiscovery
    command: [root.pluginDir + "/bin/agent-room", "models"]
    stdout: StdioCollector { onStreamFinished: root.loadGrokModels(this.text) }
  }

  Timer {
    interval: 4000
    running: window.visible
    repeat: true
    onTriggered: root.reloadHouse()
  }

  Component.onCompleted: {
    root.runCli(["init"])
    modelDiscovery.running = true
  }

  FloatingWindow {
    id: window
    title: "Agent Console"
    color: root.background
    implicitWidth: 980
    implicitHeight: 860
    minimumSize: Qt.size(720, 560)

    onVisibleChanged: {
      if (!visible && !root.closingFromHost && root.shell && typeof root.shell.hide === "function")
        root.shell.hide("io.github.franzferdinan51.agent-room")
    }

    FocusScope {
      id: focusScope
      anchors.fill: parent
      focus: true

      PanelKeyCatcher {
        id: keyCatcher
        anchors.fill: parent
        blocked: nameField.activeFocus || goalField.activeFocus || cwdField.activeFocus || workspaceField.activeFocus || programField.activeFocus || roomFilterField.activeFocus || editNameField.activeFocus || editGoalField.activeFocus || editWorkspaceField.activeFocus || composeField.activeFocus
        onCloseRequested: root.requestClose()
        onActivateRequested: {}

        Column {
          id: chrome
          anchors.fill: parent
          anchors.margins: Style.space(18)
          spacing: Style.space(14)

          Flow {
            width: parent.width
            spacing: Style.space(12)

            Text {
              text: "󱚣"
              color: root.accent
              font.family: root.fontFamily
              font.pixelSize: Style.font.title
              verticalAlignment: Text.AlignVCenter
              height: titleCol.height
            }

            Column {
              id: titleCol
              spacing: 2
              Text {
                text: "Agent Console"
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.title
                font.bold: true
              }
              Text {
                text: ((root.meta.program || "agent") + "  ·  " + (root.meta.omarchy || "omarchy")).toUpperCase()
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

            Button {
              text: "SETTINGS"
              bordered: true
              foreground: root.foreground
              onClicked: root.tab = "settings"
            }
          }

          Flow {
            width: parent.width
            height: 40
            spacing: Style.space(8)
            Repeater {
              model: [
                { id: "overview", label: "Overview" },
                { id: "health", label: "Health", count: root.stats.health || 0 },
                { id: "cmds", label: "Cmds", count: root.stats.cmds || 0 },
                { id: "context", label: "Context" },
                { id: "plan", label: "Plan", count: root.stats.plan || 0 },
                { id: "work", label: "Work", count: root.stats.active_work || 0 },
                { id: "house", label: "House", count: root.stats.teams || 0 },
                { id: "teams", label: "Teams", count: root.stats.teams || 0 },
                { id: "settings", label: "Settings" }
              ]
              delegate: Button {
                required property var modelData
                height: 36
                text: modelData.count !== undefined && modelData.count !== null
                  ? (modelData.label + "  " + modelData.count)
                  : modelData.label
                bordered: true
                selected: root.tab === modelData.id
                onClicked: root.tab = modelData.id
              }
            }
          }

          Text {
            visible: root.lastError !== ""
            width: parent.width
            wrapMode: Text.Wrap
            text: root.lastError
            color: root.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
          Text {
            visible: cli.running
            text: "Working… house state will refresh when the command finishes."
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }

          ScrollView {
            id: scrollArea
            width: parent.width
            height: parent.height - y
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            Column {
              width: scrollArea.availableWidth
              spacing: Style.space(16)

              Text {
                visible: !root.houseLoaded
                width: parent.width
                text: "Loading Agent House…"
                color: root.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }

              // ---------- OVERVIEW ----------
              Column {
                visible: root.tab === "overview"
                width: parent.width
                spacing: Style.space(12)
                PanelSectionHeader { text: "HOUSE"; foreground: root.foreground }
                Text {
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  text: "Rooms of coding agents, talking over MCP Mail, with a help board — all on disk, no web server."
                }
                StatsRow {
                  width: parent.width
                  items: [
                    { label: "TEAMS", value: String(root.stats.teams || 0), caption: "rooms in the house" },
                    { label: "RUNNING", value: String(root.stats.running || 0), caption: "active seats" },
                    { label: "MAIL", value: String(root.stats.messages || 0), caption: "visible messages" }
                  ]
                }
                Row {
                  spacing: Style.space(8)
                  Button { text: "Create room"; bordered: true; onClicked: root.tab = "house" }
                  Button { text: "Open Teams"; bordered: true; onClicked: root.tab = "teams" }
                  Button { text: "Review room"; bordered: true; onClicked: root.reviewRoom() }
                  Button { text: "Stop all"; bordered: true; enabled: root.stats.running > 0; onClicked: root.runMaintenance("stop-all") }
                  Button { text: "Refresh"; bordered: true; onClicked: root.reloadHouse() }
                  Button { text: "Settings"; bordered: true; onClicked: root.tab = "settings" }
                }
                PanelSectionHeader { text: "HERMES"; foreground: root.foreground }
                Text {
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.foreground
                  font.family: root.fontFamily
                  text: root.hermes.installed
                    ? ("Connected  ·  " + (root.hermes.model || "model unset") + "  ·  gateway " + (root.hermes.gateway || "?") + "  ·  ACP " + (root.hermes.acp ? "ready" : "not ready"))
                    : "Hermes Agent is not on PATH. Install it, then it can sit in a room over TUI or `hermes acp`."
                }
                PanelSectionHeader { text: "HARNESS MIX"; foreground: root.foreground }
                Repeater {
                  model: {
                    var mix = root.stats.harness_mix || {}
                    var rows = []
                    for (var k in mix) rows.push({ id: k, n: mix[k] })
                    return rows
                  }
                  delegate: Text {
                    required property var modelData
                    text: (modelData.id || "") + "  ·  " + (modelData.n || 0) + " seats"
                    color: root.foreground
                    font.family: root.fontFamily
                  }
                }
              }

              // ---------- HEALTH ----------
              Column {
                visible: root.tab === "health"
                width: parent.width
                spacing: Style.space(10)
                PanelSectionHeader { text: "HEALTH"; foreground: root.foreground }
                Row {
                  spacing: Style.space(8)
                  Button { text: "Refresh health"; bordered: true; onClicked: root.reloadHouse() }
                  Button { text: "Stop all teams"; bordered: true; enabled: root.stats.running > 0; onClicked: root.runMaintenance("stop-all") }
                }
                Repeater {
                  model: root.house.health || []
                  delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    implicitHeight: healthCol.height + Style.space(16)
                    color: root.card
                    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
                    border.width: 1
                    Column {
                      id: healthCol
                      x: Style.space(12)
                      y: Style.space(8)
                      width: parent.width - Style.space(24)
                      spacing: 4
                      Text {
                        text: (modelData.level || "info").toUpperCase() + "  ·  " + (modelData.title || "")
                        color: modelData.level === "error" ? root.urgent : root.accent
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption
                        font.bold: true
                      }
                      Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: modelData.message || ""
                        color: root.foreground
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.body
                      }
                    }
                  }
                }
                Text {
                  visible: (root.house.health || []).length === 0
                  text: "All clear. No stale seats, seat failures, blocked work, open help requests, or claim collisions detected."
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.dim
                  font.family: root.fontFamily
                }
              }

              // ---------- CMDS ----------
              Column {
                visible: root.tab === "cmds"
                width: parent.width
                spacing: Style.space(8)
                PanelSectionHeader { text: "COMMAND LOG"; foreground: root.foreground }
                Row {
                  spacing: Style.space(8)
                  TextField { width: parent.width - 110; placeholderText: "Filter commands…"; text: root.commandFilter; onTextChanged: root.commandFilter = text }
                  Button { text: "Clear"; bordered: true; onClicked: root.runMaintenance("clear-commands") }
                }
                Repeater {
                  model: (root.house.cmds || []).slice().reverse().filter(function(item) { return !root.commandFilter.trim() || ((item.cmd || "") + " " + (item.agent || "")).toLowerCase().indexOf(root.commandFilter.trim().toLowerCase()) >= 0 })
                  delegate: Text {
                    required property var modelData
                    width: parent.width
                    wrapMode: Text.Wrap
                    color: root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    text: (modelData.time || "") + "  " + (modelData.agent || "") + "  ·  " + (modelData.cmd || "")
                  }
                }
              }

              // ---------- CONTEXT ----------
              Column {
                visible: root.tab === "context"
                width: parent.width
                spacing: Style.space(8)
                PanelSectionHeader { text: "CONTEXT"; foreground: root.foreground }
                Row {
                  width: parent.width
                  spacing: Style.space(8)
                  TextField { width: parent.width - 100; placeholderText: "Add an operator context note…"; text: root.contextDraft; onTextChanged: root.contextDraft = text; Keys.onReturnPressed: root.addContext() }
                  Button { text: "Add"; bordered: true; onClicked: root.addContext() }
                }
                Repeater {
                  model: root.room ? (root.house.context || []).filter(function(item) { return item.room_id === root.room.id }) : []
                  delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    implicitHeight: cxCol.height + Style.space(16)
                    color: root.card
                    border.width: 1
                    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
                    Column {
                      id: cxCol
                      x: Style.space(12); y: Style.space(8)
                      width: parent.width - Style.space(24)
                      spacing: 4
                      Text {
                        text: (modelData.author || "") + "  ·  " + (modelData.time || "")
                        color: root.dim
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption
                      }
                      Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: modelData.text || ""
                        color: root.foreground
                        font.family: root.fontFamily
                      }
                    }
                  }
                }
                Text {
                  visible: root.room && !(root.house.context || []).some(function(item) { return item.room_id === root.room.id })
                  text: "No context notes yet. Agents can call context_write."
                  color: root.dim
                  font.family: root.fontFamily
                }
              }

              // ---------- PLAN ----------
              Column {
                visible: root.tab === "plan"
                width: parent.width
                spacing: Style.space(8)
                PanelSectionHeader { text: "PLAN"; foreground: root.foreground }
                Row {
                  width: parent.width
                  spacing: Style.space(8)
                  TextField { width: parent.width - 100; placeholderText: "Add a plan step…"; text: root.planDraft; onTextChanged: root.planDraft = text; Keys.onReturnPressed: root.addPlan() }
                  Button { text: "Add"; bordered: true; onClicked: root.addPlan() }
                }
                Repeater {
                  model: root.room ? (root.house.plan || []).filter(function(item) { return item.room_id === root.room.id }) : []
                  delegate: Row {
                    required property var modelData
                    width: parent.width
                    spacing: Style.space(8)
                    Text { width: parent.width - 120; wrapMode: Text.Wrap; color: modelData.status === "completed" ? root.dim : root.foreground; font.family: root.fontFamily; text: (modelData.status === "completed" ? "✓  " : "•  ") + (modelData.text || "") }
                    Button { visible: modelData.status !== "completed"; text: "Done"; bordered: true; onClicked: root.runCli(["plan-complete", modelData.id]) }
                  }
                }
                Text {
                  visible: root.room && !(root.house.plan || []).some(function(item) { return item.room_id === root.room.id })
                  text: "No plan items yet. Agents can call plan_add."
                  color: root.dim
                  font.family: root.fontFamily
                }
              }

              // ---------- WORK ----------
              Column {
                visible: root.tab === "work"
                width: parent.width
                spacing: Style.space(12)
                PanelSectionHeader { text: "AGENT WORKBENCH"; foreground: root.foreground }
                TextField { width: parent.width; placeholderText: "Task title"; text: root.workTitleDraft; onTextChanged: root.workTitleDraft = text }
                Row {
                  width: parent.width
                  spacing: Style.space(8)
                  TextField { width: parent.width - 100; placeholderText: "Task brief"; text: root.workBriefDraft; onTextChanged: root.workBriefDraft = text; Keys.onReturnPressed: root.createWork() }
                  Button { text: "Create task"; bordered: true; onClicked: root.createWork() }
                }
                StatsRow {
                  width: parent.width
                  items: [
                    { label: "ACTIVE", value: String(root.stats.active_work || 0), caption: "resumable task capsules" },
                    { label: "BLOCKED", value: String(root.stats.blocked_work || 0), caption: "need attention or input" },
                    { label: "CLAIMS", value: String(root.stats.claims || 0), caption: "coordinated file paths" }
                  ]
                }
                Text {
                  text: "TASK CAPSULES  ·  " + (root.roomWork.length)
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
                Repeater {
                  model: root.tab === "work" ? root.roomWork : []
                  delegate: Column {
                    required property var modelData
                    width: parent.width
                    spacing: Style.space(6)
                    Capsule { width: parent.width; title: modelData.title || ""; body: modelData.brief || ""; nextLine: modelData.next || ""; footer: (modelData.cwd || "") + "    " + (modelData.files || 0) + " FILES  ·  " + (modelData.claims || 0) + " CLAIMS"; statusText: ((modelData.status || "") + "  ·  " + (modelData.owner || "")).toUpperCase(); statusColor: modelData.status === "active" ? root.accent : root.dim }
                    Flow {
                      width: parent.width
                      spacing: Style.space(8)
                      Button {
                        text: "Claim"
                        bordered: true
                        enabled: modelData.status !== "completed"
                        onClicked: root.runCli(["claim-work", modelData.id, "--agent", "operator"])
                      }
                      Button {
                        text: "Complete"
                        bordered: true
                        enabled: modelData.status !== "completed"
                        onClicked: root.runCli(["complete-work", modelData.id, "--agent", "operator"])
                      }
                    }
                  }
                }
                Text {
                  visible: root.roomWork.length === 0
                  text: "No task capsules in this room yet."
                  color: root.dim
                  font.family: root.fontFamily
                }
              }

              // ---------- HOUSE / CREATE ROOM ----------
              Column {
                visible: root.tab === "house"
                width: parent.width
                spacing: Style.space(12)
                PanelSectionHeader { text: "CREATE A ROOM"; foreground: root.foreground }
                Text {
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.dim
                  font.family: root.fontFamily
                  text: "A room is a named goal plus seats. Starting it opens each agent in the current workspace unless you choose a number or name below. They talk with MCP Mail and can ask for help on the board."
                }
                Text { text: "NAME"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true }
                TextField {
                  id: nameField
                  width: parent.width
                  placeholderText: "Superprompt"
                  text: root.formName
                  onTextChanged: root.formName = text
                }
                Text { text: "GOAL"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true }
                TextField {
                  id: goalField
                  width: parent.width
                  placeholderText: "What should the team deliver?"
                  text: root.formGoal
                  onTextChanged: root.formGoal = text
                }
                Text { text: "WORKING DIRECTORY"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true }
                TextField {
                  id: cwdField
                  width: parent.width
                  text: root.formCwd
                  onTextChanged: root.formCwd = text
                }
                Text { text: "TERMINAL WORKSPACE"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true }
                TextField {
                  id: workspaceField
                  width: parent.width
                  placeholderText: root.settingsWorkspace || "current"
                  text: root.formWorkspace
                  onTextChanged: root.formWorkspace = text
                }
                Text { width: parent.width; wrapMode: Text.Wrap; text: "Use current for the page you are on, a number such as 2 or 4, or a name such as name:dev."; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
                Text { text: "PROGRAM (blank = default agent)"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true }
                TextField {
                  id: programField
                  width: parent.width
                  placeholderText: root.meta.program || "grok"
                  text: root.formProgram
                  onTextChanged: root.formProgram = text
                }
                Toggle { width: parent.width; label: "Coordinator"; description: "Routes work and synthesizes the result"; checked: root.formCoordinator; onClicked: root.formCoordinator = !root.formCoordinator }
                Row {
                  visible: root.formCoordinator
                  spacing: Style.space(8)
                  width: parent.width
                  Dropdown { width: parent.width / 2 - 4; label: "Harness"; value: root.formHCoordinator; options: root.harnessOptions; onChanged: function(v) { root.formHCoordinator = v } }
                  Dropdown { width: parent.width / 2 - 4; label: "Transport"; value: root.formTCoordinator; options: root.transportOptions; onChanged: function(v) { root.formTCoordinator = v } }
                }
                Toggle { width: parent.width; label: "Builder"; description: "Implements the assignment"; checked: root.formBuilder; onClicked: root.formBuilder = !root.formBuilder }
                Row {
                  visible: root.formBuilder
                  spacing: Style.space(8)
                  width: parent.width
                  Dropdown { width: parent.width / 2 - 4; label: "Harness"; value: root.formHBuilder; options: root.harnessOptions; onChanged: function(v) { root.formHBuilder = v } }
                  Dropdown { width: parent.width / 2 - 4; label: "Transport"; value: root.formTBuilder; options: root.transportOptions; onChanged: function(v) { root.formTBuilder = v } }
                }
                Toggle { width: parent.width; label: "Reviewer"; description: "Reads the work and files findings"; checked: root.formReviewer; onClicked: root.formReviewer = !root.formReviewer }
                Row {
                  visible: root.formReviewer
                  spacing: Style.space(8)
                  width: parent.width
                  Dropdown { width: parent.width / 2 - 4; label: "Harness"; value: root.formHReviewer; options: root.harnessOptions; onChanged: function(v) { root.formHReviewer = v } }
                  Dropdown { width: parent.width / 2 - 4; label: "Transport"; value: root.formTReviewer; options: root.transportOptions; onChanged: function(v) { root.formTReviewer = v } }
                }
                Toggle { width: parent.width; label: "Judge"; description: "Acceptance criteria and keep/remove"; checked: root.formJudge; onClicked: root.formJudge = !root.formJudge }
                Row {
                  visible: root.formJudge
                  spacing: Style.space(8)
                  width: parent.width
                  Dropdown { width: parent.width / 2 - 4; label: "Harness"; value: root.formHJudge; options: root.harnessOptions; onChanged: function(v) { root.formHJudge = v } }
                  Dropdown { width: parent.width / 2 - 4; label: "Transport"; value: root.formTJudge; options: root.transportOptions; onChanged: function(v) { root.formTJudge = v } }
                }
                Toggle { width: parent.width; label: "Creative-director"; description: "Novelty and framing"; checked: root.formCreative; onClicked: root.formCreative = !root.formCreative }
                Row {
                  visible: root.formCreative
                  spacing: Style.space(8)
                  width: parent.width
                  Dropdown { width: parent.width / 2 - 4; label: "Harness"; value: root.formHCreative; options: root.harnessOptions; onChanged: function(v) { root.formHCreative = v } }
                  Dropdown { width: parent.width / 2 - 4; label: "Transport"; value: root.formTCreative; options: root.transportOptions; onChanged: function(v) { root.formTCreative = v } }
                }
                Row {
                  spacing: Style.space(8)
                  Button { text: "Create room"; bordered: true; onClicked: root.createRoom() }
                  Button { text: "Create and start"; bordered: true; onClicked: { root.startAfterCreate = true; root.createRoom() } }
                }

                Row {
                  width: parent.width
                  spacing: Style.space(8)
                  PanelSectionHeader { text: "ROOMS  ·  " + root.rooms.length; foreground: root.foreground }
                  Item { width: Math.max(0, parent.width - 190); height: 1 }
                  Button { text: "Refresh"; bordered: true; onClicked: root.reloadHouse() }
                }
                TextField {
                  id: roomFilterField
                  width: parent.width
                  placeholderText: "Filter teams by name, goal, or status…"
                  text: root.roomFilter
                  onTextChanged: root.roomFilter = text
                }
                Repeater {
                  model: root.filteredRooms
                  delegate: Button {
                    required property var modelData
                    width: parent.width
                    leftAlign: true
                    bordered: true
                    selected: root.selectedRoom === modelData.index
                    text: (modelData.room.name || "") + "  ·  " + (modelData.room.status || "idle") + "  ·  " + ((modelData.room.roles || []).length) + " seats\n" + (modelData.room.goal || "")
                    onClicked: root.selectRoomForEdit(modelData.index)
                  }
                }
                Text {
                  visible: root.rooms.length > 0 && root.filteredRooms.length === 0
                  text: "No teams match this filter."
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                }
                Column {
                  visible: !!root.editRoomId
                  width: parent.width
                  spacing: Style.space(8)
                  PanelSectionHeader { text: "EDIT SELECTED TEAM"; foreground: root.foreground }
                  TextField {
                    id: editNameField
                    width: parent.width
                    placeholderText: "Team name"
                    text: root.editRoomName
                    onTextChanged: root.editRoomName = text
                  }
                  TextField {
                    id: editGoalField
                    width: parent.width
                    placeholderText: "Team goal"
                    text: root.editRoomGoal
                    onTextChanged: root.editRoomGoal = text
                  }
                  TextField {
                    id: editWorkspaceField
                    width: parent.width
                    placeholderText: "Terminal workspace (2, 4, or name:dev)"
                    text: root.editRoomWorkspace
                    onTextChanged: root.editRoomWorkspace = text
                  }
                  Text {
                    width: parent.width
                    text: root.deleteArmed ? "Click Confirm delete to remove this team and its messages, work, claims, plan, and context." : "Changes apply to the selected team."
                    color: root.deleteArmed ? root.urgent : root.dim
                    wrapMode: Text.Wrap
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                  }
                  Flow {
                    width: parent.width
                    spacing: Style.space(8)
                    Button { text: "Save changes"; bordered: true; onClicked: root.editSelectedRoom() }
                    Button { text: "Open chat"; bordered: true; onClicked: root.tab = "teams" }
                    Button { text: root.deleteArmed ? "Confirm delete" : "Delete team"; bordered: true; onClicked: root.deleteSelectedRoom() }
                    Button { visible: root.deleteArmed; text: "Cancel"; bordered: true; onClicked: root.deleteArmed = false }
                  }
                }
              }

              // ---------- TEAMS ----------
              Column {
                visible: root.tab === "teams"
                width: parent.width
                spacing: Style.space(12)

                PanelSectionHeader { text: "AGENT TEAMS"; foreground: root.foreground }
                StatsRow {
                  width: parent.width
                  items: [
                    { label: "TEAMS", value: String(root.stats.teams || 0), caption: "coordinated goals" },
                    { label: "RUNNING", value: String(root.stats.running || 0), caption: "active agents" },
                    { label: "CHAT", value: String(root.roomMail.length), caption: "visible messages" }
                  ]
                }

                Text {
                  visible: !!root.room
                  text: "TEAM MONITOR  ·  " + (root.rooms.length)
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
                Text {
                  visible: !!root.room
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  text: "Follow Room Mail as one chat, watch every assignment, and find the coordinator's integrated result without the House administration noise."
                }

                Capsule {
                  visible: !!root.room && !(root.room && root.room.monitor_hidden)
                  width: parent.width
                  title: root.room ? (root.room.name || "") : ""
                  body: root.room ? (root.room.goal || "") : ""
                  nextLine: ""
                  footer: root.roleLine()
                  statusText: root.room
                    ? ((root.room.status || "idle").toUpperCase() + "  ·  " + root.doneRoles + "/" + ((root.room.roles || []).length) + " DONE")
                    : ""
                  statusColor: root.room && root.room.status === "running" ? root.accent : root.dim
                }

                Flow {
                  visible: !!root.room
                  width: parent.width
                  spacing: Style.space(8)
                  Button {
                    text: "Start team"
                    bordered: true
                    enabled: root.room && root.room.status !== "running"
                    onClicked: root.startSelected()
                  }
                  Button {
                    text: "▣  Coordinator"
                    bordered: true
                    onClicked: root.startSelected()
                  }
                  Button {
                    text: root.room && root.room.monitor_hidden ? "Show monitor" : "▾  Hide monitor"
                    bordered: true
                    onClicked: root.hideMonitor()
                  }
                  Button {
                    text: "Stop team"
                    bordered: true
                    enabled: root.room && root.room.status === "running"
                    onClicked: root.stopSelected()
                  }
                  Button { text: "Edit team"; bordered: true; onClicked: root.editCurrentRoom() }
                }

                Text {
                  visible: !!root.room
                  text: "SEATS  ·  switch harness or TUI/ACP per agent"
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
                Repeater {
                  model: root.room ? (root.room.roles || []) : []
                  delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    implicitHeight: seatColumn.implicitHeight + Style.space(24)
                    color: root.card
                    border.width: 1
                    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
                    Column {
                      id: seatColumn
                      x: Style.space(12)
                      y: Style.space(12)
                      width: parent.width - Style.space(24)
                      spacing: Style.space(8)
                      Column {
                        width: parent.width
                        spacing: 2
                        Text {
                          text: modelData.name || modelData.id
                          color: root.foreground
                          font.family: root.fontFamily
                          font.bold: true
                        }
                        Text {
                          text: (modelData.harness || modelData.program || "") + "  ·  " + (modelData.transport || "tui") + "  ·  " + (modelData.status || "idle")
                          color: root.dim
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                        }
                      }
                      Dropdown {
                        width: parent.width
                        label: "Model"
                        value: modelData.model || root.settingsDefaultModel
                        options: root.modelOptionsFor(modelData.harness || modelData.program || root.settingsDefaultHarness)
                        onChanged: function(v) { root.setSeatModel(modelData.id, v) }
                      }
                      Flow {
                        width: parent.width
                        spacing: Style.space(8)
                        Button {
                          text: modelData.status === "running" ? "Stop" : "Start"
                          bordered: true
                          onClicked: {
                            if (!root.room) return
                            root.runCli([modelData.status === "running" ? "stop-seat" : "start-seat", root.room.id, modelData.id])
                          }
                        }
                        Button { text: "Grok"; bordered: true; selected: (modelData.harness || modelData.program) === "grok"; onClicked: root.switchSeat(modelData.id, "grok", modelData.transport || "tui") }
                        Button { text: "Codex"; bordered: true; selected: (modelData.harness || modelData.program) === "codex"; onClicked: root.switchSeat(modelData.id, "codex", modelData.transport || "tui") }
                        Button { text: "Hermes"; bordered: true; selected: (modelData.harness || modelData.program) === "hermes"; onClicked: root.switchSeat(modelData.id, "hermes", modelData.transport || "tui") }
                        Button { text: (modelData.transport === "acp") ? "Use TUI" : "Use ACP"; bordered: true; onClicked: root.switchSeat(modelData.id, modelData.harness || modelData.program, modelData.transport === "acp" ? "tui" : "acp") }
                      }
                    }
                  }
                }

                Text {
                  visible: !!root.room && (root.room.roles || []).length === 0
                  width: parent.width
                  text: "This team has no seats yet. Edit the team from House to add one."
                  color: root.dim
                  font.family: root.fontFamily
                  wrapMode: Text.Wrap
                }
                Text {
                  visible: !root.room && root.rooms.length === 0
                  width: parent.width
                  text: "No teams yet. Open House to create your first team."
                  color: root.dim
                  font.family: root.fontFamily
                  wrapMode: Text.Wrap
                }

                Text {
                  visible: !!root.room
                  text: "TEAM CHAT  ·  " + root.roomMail.length + " MESSAGES"
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }

                Repeater {
                  model: root.tab === "teams" ? root.roomMail : []
                  delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    implicitHeight: mailCol.height + Style.space(20)
                    color: root.card
                    border.width: 1
                    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
                    Column {
                      id: mailCol
                      x: Style.space(14)
                      y: Style.space(10)
                      width: parent.width - Style.space(28)
                      spacing: 6
                      Row {
                        width: parent.width
                        Text {
                          text: (modelData.room || "") + "  ·  " + (modelData.from || "")
                          color: root.foreground
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.body
                          font.bold: true
                        }
                        Item { width: 12; height: 1 }
                        Text {
                          text: modelData.time || ""
                          color: root.dim
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                        }
                      }
                      Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: (modelData.subject ? (modelData.subject + " — ") : "") + (modelData.body || "")
                        color: root.foreground
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.body
                      }
                    }
                  }
                }

                Text {
                  visible: !!root.room
                  text: "HELP BOARD  ·  " + root.roomBoard.length
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
                Repeater {
                  model: root.tab === "teams" ? root.roomBoard : []
                  delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    implicitHeight: bdCol.height + Style.space(18)
                    color: root.card
                    border.width: 1
                    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
                    Column {
                      id: bdCol
                      x: Style.space(14); y: Style.space(10)
                      width: parent.width - Style.space(28)
                      spacing: 4
                      Text {
                        text: ((modelData.status || "open").toUpperCase()) + "  ·  " + (modelData.author || "") + "  ·  " + (modelData.title || "")
                        color: root.accent
                        font.family: root.fontFamily
                        font.bold: true
                      }
                      Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: modelData.body || ""
                        color: root.foreground
                        font.family: root.fontFamily
                      }
                    }
                  }
                }

                Row {
                  visible: !!root.room
                  spacing: Style.space(8)
                  width: parent.width
                  TextField {
                    id: composeField
                    width: parent.width - 88
                    placeholderText: "Mail the room…"
                    text: root.composeText
                    onTextChanged: root.composeText = text
                    Keys.onReturnPressed: root.sendCompose()
                  }
                  Button { text: "Send"; bordered: true; onClicked: root.sendCompose() }
                }

                Text {
                  visible: !root.room
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.dim
                  font.family: root.fontFamily
                  text: "No rooms yet. Open the House tab and create one."
                }
                Button {
                  visible: !root.room
                  text: "Create your first room"
                  bordered: true
                  onClicked: root.tab = "house"
                }
              }

              // ---------- SETTINGS ----------
              Column {
                visible: root.tab === "settings"
                width: parent.width
                spacing: Style.space(12)
                PanelSectionHeader { text: "TELEGRAM CONNECTOR"; foreground: root.foreground }
                Text {
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.dim
                  font.family: root.fontFamily
                  text: "Connect a Telegram bot to a team. Tokens stay in the desktop keyring when available and are never written to the Agent Room snapshot."
                }
                TextField {
                  width: parent.width
                  placeholderText: root.telegramStatus.configured ? "Token saved — enter a new token to replace it" : "BotFather token"
                  echoMode: TextInput.Password
                  text: root.telegramToken
                  onTextChanged: root.telegramToken = text
                }
                Flow {
                  width: parent.width
                  spacing: Style.space(8)
                  Button { text: "Save token"; bordered: true; onClicked: root.telegramAction("set-token") }
                  Button { text: "Test"; bordered: true; onClicked: root.telegramAction("test") }
                  Button { text: "Connect"; bordered: true; enabled: root.telegramStatus.configured && !root.telegramStatus.polling; onClicked: root.telegramAction("start") }
                  Button { text: "Pause"; bordered: true; enabled: root.telegramStatus.polling; onClicked: root.telegramAction("stop") }
                  Button { text: "Forget token"; bordered: true; enabled: root.telegramStatus.configured; onClicked: root.telegramAction("forget-token") }
                }
                Text {
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.telegramStatus.status === "error" ? root.urgent : root.foreground
                  font.family: root.fontFamily
                  text: "Status: " + (root.telegramStatus.status || "disconnected") + "  ·  polling: " + (root.telegramStatus.polling ? "on" : "off") + (root.telegramStatus.bot && root.telegramStatus.bot.username ? "  ·  @" + root.telegramStatus.bot.username : "") + (root.telegramStatus.error ? "\n" + root.telegramStatus.error : "")
                }
                Dropdown { width: parent.width; label: "Telegram team"; value: root.telegramTeam; options: root.telegramTeamOptions; onChanged: function(v) { root.telegramTeam = v } }
                Toggle { width: parent.width; label: "Auto-approve chats"; description: "Allow new chats without manual pairing (less secure)"; checked: root.telegramAutoApprove; onClicked: root.telegramAutoApprove = !root.telegramAutoApprove }
                PanelSectionHeader { text: "PAIRING REQUESTS  ·  " + (root.telegramState.pending || []).length; foreground: root.foreground }
                Repeater {
                  model: root.telegramState.pending || []
                  delegate: Row {
                    required property var modelData
                    width: parent.width
                    spacing: Style.space(8)
                    Text { width: parent.width - 170; text: (modelData.name || modelData.username || "Telegram chat") + "  ·  " + modelData.chat_id; color: root.foreground; font.family: root.fontFamily; elide: Text.ElideRight }
                    Button { text: "Approve"; bordered: true; onClicked: root.telegramApprove(modelData.chat_id) }
                    Button { text: "Deny"; bordered: true; onClicked: root.telegramDeny(modelData.chat_id) }
                  }
                }
                Text { visible: (root.telegramState.pending || []).length === 0; text: "No pending Telegram chats."; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
                PanelSectionHeader { text: "HARNESSES"; foreground: root.foreground }
                Text {
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.dim
                  font.family: root.fontFamily
                  text: "A room can mix Grok Build, Codex, Claude Code, Hermes, and the rest. TUI opens a terminal. ACP talks Agent Client Protocol over stdio — including `grok agent stdio` and `hermes acp`."
                }
                Dropdown { width: parent.width; label: "Default harness"; value: root.settingsDefaultHarness; options: root.harnessOptions; onChanged: function(v) { root.settingsDefaultHarness = v } }
                Dropdown { width: parent.width; label: "Default model"; value: root.settingsDefaultModel; options: root.modelOptions; onChanged: function(v) { root.settingsDefaultModel = v } }
                Dropdown { width: parent.width; label: "Default transport"; value: root.settingsDefaultTransport; options: root.transportOptions; onChanged: function(v) { root.settingsDefaultTransport = v } }
                Toggle { width: parent.width; label: "Mixed harness rooms"; description: "Allow each seat its own CLI"; checked: root.settingsMixed; onClicked: root.settingsMixed = !root.settingsMixed }
                Toggle { width: parent.width; label: "ACP enabled"; description: "Spawn seats with Agent Client Protocol adapters"; checked: root.settingsAcp; onClicked: root.settingsAcp = !root.settingsAcp }
                Toggle { width: parent.width; label: "Hermes enabled"; description: "Treat Hermes Agent as a first-class seat and show gateway status"; checked: root.settingsHermes; onClicked: root.settingsHermes = !root.settingsHermes }
                Text { text: "WORKSPACE"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true }
                TextField {
                  width: parent.width
                  text: root.settingsWorkspace
                  onTextChanged: root.settingsWorkspace = text
                }
                Button { text: "Save settings"; bordered: true; onClicked: root.saveSettings() }
                Text { text: "DANGER ZONE"; color: root.urgent; font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true; topPadding: Style.space(10) }
                Text { width: parent.width; wrapMode: Text.Wrap; text: root.pendingMaintenance !== "" ? "Click the action again to confirm. This cannot be undone." : "Clear messages removes MCP Mail and help-board posts. Reset house removes rooms, work, and claims but keeps these settings."; color: root.pendingMaintenance !== "" ? root.urgent : root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.caption }
                Flow { width: parent.width; spacing: Style.space(8)
                  Button { text: root.pendingMaintenance === "clear-messages" ? "Confirm clear messages" : "Clear all messages"; bordered: true; onClicked: root.runMaintenance("clear-messages") }
                  Button { text: root.pendingMaintenance === "reset-house" ? "Confirm reset house" : "Reset house"; bordered: true; onClicked: root.runMaintenance("reset-house") }
                  Button { visible: root.pendingMaintenance !== ""; text: "Cancel"; bordered: true; onClicked: root.pendingMaintenance = "" }
                }

                PanelSectionHeader { text: "HERMES CONNECTION"; foreground: root.foreground }
                Text {
                  width: parent.width
                  wrapMode: Text.Wrap
                  color: root.foreground
                  font.family: root.fontFamily
                  text: root.hermes.installed
                    ? ((root.hermes.version || "Hermes") + "\nmodel  " + (root.hermes.model || "—") + "\ngateway  " + (root.hermes.gateway || "—") + "\nACP  " + (root.hermes.acp ? "ready (`hermes acp`)" : "adapter missing") + "\n" + (root.hermes.path || ""))
                    : "Hermes is not installed. After `hermes` is on PATH, seats can launch `hermes --yolo` (TUI) or `hermes acp` (ACP)."
                }

                PanelSectionHeader { text: "ACP ADAPTERS"; foreground: root.foreground }
                Repeater {
                  model: root.house.acp || []
                  delegate: Text {
                    required property var modelData
                    width: parent.width
                    wrapMode: Text.Wrap
                    color: root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    text: (modelData.label || modelData.id) + "  ·  " + (modelData.installed ? "installed" : "missing") + "  ·  " + (modelData.acp_ready ? "ACP ready" : "no ACP") + (modelData.acp_command ? ("  ·  " + modelData.acp_command) : "")
                  }
                }
                PanelSectionHeader { text: "INSTALLED CLIS"; foreground: root.foreground }
                Repeater {
                  model: root.house.harnesses || []
                  delegate: Text {
                    required property var modelData
                    color: modelData.installed ? root.foreground : root.dim
                    font.family: root.fontFamily
                    text: (modelData.installed ? "●  " : "○  ") + (modelData.label || modelData.id) + "  ·  " + (modelData.family || "")
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  function roleLine() {
    if (!room) return ""
    var parts = []
    var roles = room.roles || []
    for (var i = 0; i < roles.length; i++) {
      var r = roles[i]
      parts.push((r.name || r.id).toUpperCase() + "  ·  " + String(r.status || "idle").toUpperCase())
    }
    return parts.join("   ")
  }

  component StatsRow: Flow {
    id: statsRow
    property var items: []
    spacing: Style.space(10)
    Repeater {
      model: statsRow.items
      delegate: Rectangle {
        required property var modelData
        // Flow keeps the cards usable when the window becomes narrow instead
        // of forcing a row wider than the viewport.
        width: Math.max(120, Math.min(280, (statsRow.width - Style.space(20)) / Math.max(1, statsRow.items.length)))
        implicitHeight: 86
        color: root.card
        border.width: 1
        border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
        Column {
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.margins: Style.space(14)
          spacing: 2
          Text {
            text: modelData.label || ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }
          Text {
            text: modelData.value || "0"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
          }
          Text {
            text: modelData.caption || ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }
    }
  }

  component Capsule: Rectangle {
    property string title: ""
    property string body: ""
    property string nextLine: ""
    property string footer: ""
    property string statusText: ""
    property color statusColor: root.accent
    color: root.card
    border.width: 1
    border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.18)
    implicitHeight: capCol.height + Style.space(24)
    Column {
      id: capCol
      x: Style.space(16)
      y: Style.space(12)
      width: parent.width - Style.space(32)
      spacing: 8
      Row {
        width: parent.width
        Text {
          width: parent.width - 180
          wrapMode: Text.Wrap
          text: title
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.title
          font.bold: true
        }
      }
      Text {
        anchors.right: capCol.right
        text: statusText
        color: statusColor
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: true
      }
      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: body
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }
      Text {
        visible: nextLine !== ""
        width: parent.width
        wrapMode: Text.Wrap
        text: "NEXT  " + nextLine
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
      Text {
        width: parent.width
        wrapMode: Text.Wrap
        text: footer
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
  }
}
