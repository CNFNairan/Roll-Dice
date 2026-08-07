const socket = io();
let currentUsername = "";
let currentRoom = "";
let isGM = false;
let currentPage = "mesa";

window.onload = function () {
  const savedUser = localStorage.getItem("rpg_username");
  const savedRoom = localStorage.getItem("rpg_room");
  const savedGM = localStorage.getItem("rpg_is_gm") === "true";

  if (savedUser) document.getElementById("username").value = savedUser;
  if (savedRoom) document.getElementById("room").value = savedRoom;
  if (savedGM) document.getElementById("enter-as-gm").checked = savedGM;

  if (savedUser && savedRoom) {
    entrarNaMesa(true);
  }
};

function entrarNaMesa(isAuto = false) {
  const user = document.getElementById("username").value.trim();
  const room = document.getElementById("room").value.trim();
  const wantGM = document.getElementById("enter-as-gm").checked;

  if (!user || !room) {
    if (!isAuto) alert("Preencha o seu nome e o nome da mesa!");
    return;
  }

  localStorage.setItem("rpg_username", user);
  localStorage.setItem("rpg_room", room);
  localStorage.setItem("rpg_is_gm", wantGM);

  socket.emit("join_room", { username: user, room: room, is_gm: wantGM });
}

function sairDaMesa() {
  localStorage.removeItem("rpg_room");
  localStorage.removeItem("rpg_is_gm");
  location.reload();
}

function showPage(pageName) {
  currentPage = pageName === "conversa" ? "conversa" : "mesa";

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.page === currentPage);
  });

  document
    .getElementById("page-mesa")
    .classList.toggle("active", currentPage === "mesa");
  document
    .getElementById("page-conversa")
    .classList.toggle("active", currentPage === "conversa");
}

function enviarRolagem() {
  const input = document.getElementById("command-input");
  const expressao = input.value.trim();
  const ocultoCheck = document.getElementById("oculto-check");
  const isOculto = ocultoCheck ? ocultoCheck.checked : false;

  if (!expressao) return;

  const regexRolagem = /(^|\s|\b)(\d*d\d+|r\(|#)/i;
  const regexMatematica = /^[0-9+\-*/(). ]+$/;

  if (regexRolagem.test(expressao) || regexMatematica.test(expressao)) {
    socket.emit("send_roll", {
      room: currentRoom,
      username: currentUsername,
      expressao: expressao,
      is_oculto: isOculto,
    });
  } else {
    socket.emit("send_text_chat", {
      room: currentRoom,
      username: currentUsername,
      message: expressao,
    });

    showPage("conversa");
  }

  input.value = "";
}

function enviarMensagemDiretaChat() {
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;

  socket.emit("send_text_chat", {
    room: currentRoom,
    username: currentUsername,
    message: msg,
  });

  input.value = "";
}

function limparChat() {
  if (
    confirm(
      "Tem certeza que deseja apagar todo o histórico de rolagens da mesa?",
    )
  ) {
    socket.emit("clear_chat", {
      room: currentRoom,
      username: currentUsername,
    });
  }
}

function travarChat() {
  socket.emit("toggle_chat_lock", {
    room: currentRoom,
    username: currentUsername,
  });
}

function atualizarInterfaceChat(isLocked) {
  const input = document.getElementById("command-input");
  const btn = document.getElementById("btn-rolar");
  const btnLock = document.getElementById("btn-lock-chat");

  if (isLocked) {
    if (btnLock) {
      btnLock.innerHTML = "Destravar Logs 🔓";
      btnLock.style.background = "#10b981";
    }
    if (!isGM) {
      input.disabled = true;
      btn.disabled = true;
      input.placeholder = "O mestre travou as rolagens...";
    }
  } else {
    if (btnLock) {
      btnLock.innerHTML = "Travar Logs 🔒";
      btnLock.style.background = "#f59e0b";
    }
    input.disabled = false;
    btn.disabled = false;
    input.placeholder = "Ex: 1d20+5 (Rolagem) ou 'Olá grupo!' (Chat)";
  }
}

function toggleCombate() {
  socket.emit("update_combat_state", {
    room: currentRoom,
    username: currentUsername,
    action: "toggle_combat",
  });
}

function proximoTurno() {
  socket.emit("update_combat_state", {
    room: currentRoom,
    username: currentUsername,
    action: "next_turn",
  });
}

function adicionarCombatente() {
  const name = document.getElementById("npc-name").value.trim();
  const init = document.getElementById("npc-init").value.trim();
  if (!name) return;
  socket.emit("update_combat_state", {
    room: currentRoom,
    username: currentUsername,
    action: "add_combatant",
    name: name,
    init: init || 0,
  });
  document.getElementById("npc-name").value = "";
  document.getElementById("npc-init").value = "";
}

function removerCombatente(index) {
  socket.emit("update_combat_state", {
    room: currentRoom,
    username: currentUsername,
    action: "remove_combatant",
    index: index,
  });
}

function liberarMestre() {
  socket.emit("leave_gm", {
    room: currentRoom,
    username: currentUsername,
  });
}

socket.on("join_error", function (data) {
  alert(data.msg);
});

socket.on("join_success", function (data) {
  currentUsername = data.username;
  currentRoom = data.room;
  isGM = data.is_gm;

  document.getElementById("login-card").style.display = "none";
  document.getElementById("app-shell").style.display = "flex";
  document.getElementById("btn-change-room").style.display = "inline-block";

  if (isGM) {
    document.getElementById("gm-panel").style.display = "block";
  } else {
    document.getElementById("gm-panel").style.display = "none";
  }
  document.getElementById("sidebar-room-name").textContent = data.room;
  document.getElementById("sidebar-user-name").textContent = data.username;
  showPage("mesa");
  atualizarInterfaceChat(data.chat_locked);
});

socket.on("gm_status_changed", function (data) {
  isGM = data.is_gm;
  document.getElementById("gm-panel").style.display = "none";
  localStorage.setItem("rpg_is_gm", false);
});

socket.on("system_message", function (data) {
  const log = document.getElementById("chat-log");
  log.innerHTML += `<div class="system-msg">${data.msg}</div>`;
  log.scrollTop = log.scrollHeight;
});

socket.on("chat_cleared", function (data) {
  const log = document.getElementById("chat-log");
  const textLog = document.getElementById("text-chat-log");
  log.innerHTML = `<div class="system-msg">${data.msg}</div>`;
  if (textLog) {
    textLog.innerHTML = "";
  }
});

socket.on("chat_lock_updated", function (data) {
  atualizarInterfaceChat(data.locked);
  const log = document.getElementById("chat-log");
  log.innerHTML += `<div class="system-msg" style="color: #f59e0b;">${data.msg}</div>`;
  log.scrollTop = log.scrollHeight;
});

socket.on("update_players", function (players) {
  const containers = [
    document.getElementById("player-list-container"),
    document.getElementById("sidebar-player-list"),
  ];

  players.sort((a, b) => (b.is_gm === true) - (a.is_gm === true));

  const uniquePlayers = [];
  const seen = new Set();
  for (const p of players) {
    if (!seen.has(p.username)) {
      seen.add(p.username);
      uniquePlayers.push(p);
    }
  }

  containers.forEach((container) => {
    if (!container) return;
    container.innerHTML = "";
    uniquePlayers.forEach((p) => {
      const isMe = p.username === currentUsername ? " (Você)" : "";
      if (p.is_gm) {
        container.innerHTML += `<div class="player-item gm-highlight">👑 ${p.username}${isMe}</div>`;
      } else {
        container.innerHTML += `<div class="player-item">🎲 ${p.username}${isMe}</div>`;
      }
    });
  });
});

socket.on("load_history", function (historyList) {
  const log = document.getElementById("chat-log");
  log.innerHTML = "";
  historyList.forEach((data) => {
    const cardClass = data.is_oculto ? "message-card oculto" : "message-card";
    log.innerHTML += `
      <div class="${cardClass}">
        <div class="user-header">${data.username}</div>
        <div>${data.html}</div>
      </div>
    `;
  });
  log.scrollTop = log.scrollHeight;
});

socket.on("receive_roll", function (data) {
  const log = document.getElementById("chat-log");
  const cardClass = data.is_oculto ? "message-card oculto" : "message-card";
  log.innerHTML += `
    <div class="${cardClass}">
      <div class="user-header">${data.username}</div>
      <div>${data.html}</div>
    </div>
  `;
  log.scrollTop = log.scrollHeight;
});

socket.on("load_chat_history", function (chatHistory) {
  const log = document.getElementById("text-chat-log");
  log.innerHTML = "";
  chatHistory.forEach((data) => {
    log.innerHTML += `
      <div class="text-message-card">
        <div class="user-header">${data.username}</div>
        <div style="font-size: 14px; word-wrap: break-word; line-height: 1.4;">${data.message}</div>
      </div>
    `;
  });
  log.scrollTop = log.scrollHeight;
});

socket.on("receive_text_chat", function (data) {
  const log = document.getElementById("text-chat-log");
  log.innerHTML += `
    <div class="text-message-card">
      <div class="user-header">${data.username}</div>
      <div style="font-size: 14px; word-wrap: break-word; line-height: 1.4;">${data.message}</div>
    </div>
  `;
  log.scrollTop = log.scrollHeight;
});

socket.on("update_combat", function (combat) {
  const bar = document.getElementById("initiative-bar");
  const chipsContainer = document.getElementById("turn-chips");
  const statusText = document.getElementById("combat-status");
  const sidebarStatus = document.getElementById("sidebar-combat-status");
  const btnToggle = document.getElementById("btn-toggle-combat");

  if (combat.order.length > 0 || combat.active) {
    bar.style.display = "block";
  } else {
    bar.style.display = "none";
  }

  if (combat.active) {
    const activeText = "EM COMBATE ⚔️";
    if (statusText) {
      statusText.innerText = activeText;
      statusText.style.color = "#22c55e";
    }
    if (sidebarStatus) {
      sidebarStatus.innerText = activeText;
      sidebarStatus.style.color = "#22c55e";
    }
    if (btnToggle) btnToggle.innerText = "Encerrar Combate 🕊️";
  } else {
    const inactiveText = "FORA DE COMBATE";
    if (statusText) {
      statusText.innerText = inactiveText;
      statusText.style.color = "#ef4444";
    }
    if (sidebarStatus) {
      sidebarStatus.innerText = inactiveText;
      sidebarStatus.style.color = "#ef4444";
    }
    if (btnToggle) btnToggle.innerText = "Iniciar Combate ⚔️";
  }

  chipsContainer.innerHTML = "";
  combat.order.forEach((c, idx) => {
    const isActive = combat.active && idx === combat.turn_index;
    const chipClass = isActive ? "turn-chip active" : "turn-chip";
    let removeBtn = isGM
      ? `<span onclick="removerCombatente(${idx})" style="cursor:pointer; color:#ef4444; margin-left:4px;">✕</span>`
      : "";
    chipsContainer.innerHTML += `
      <div class="${chipClass}">
        <span>${c.name} (${c.init})</span>
        ${removeBtn}
      </div>
    `;
  });
});
