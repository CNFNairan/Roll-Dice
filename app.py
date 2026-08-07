from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import random
import re

app = Flask(__name__)
app.config["SECRET_KEY"] = "sua_chave_secreta_rpg_123"
socketio = SocketIO(app, cors_allowed_origins="*")

ROOM_HISTORY_LIMIT = 50
CHAT_HISTORY_LIMIT = 100

# --- MEMÓRIA RAM POR SALA ---
room_masters = {}  # {"sala": "nome_do_mestre"}
room_combats = {}  # {"sala": {"active": False, "turn_index": 0, "order": [...]}}
room_histories = {}  # {"sala": [{"public": ..., "gm_private": ...}]}
room_chat_locked = {}  # {"sala": True/False}
room_text_chats = {}  # {"sala": [{"username": ..., "message": ...}]}

user_sessions = {}  # {sid: {"room": room, "username": username}}
room_players = {}  # {"sala": {sid: {"username": username, "is_gm": bool}}}


class DiceRoller:
    def __init__(self):
        self.dice_pattern = re.compile(r"(?i)(\d*)d(\d+)(?:dl(\d+))?((?:[*/]\s*\d+(?:\.\d+)?)*)")
        self.allowed_chars = set("0123456789+-*/(). ")

    def _get_repetitions(self, text):
        if "#" not in text:
            return 1

        try:
            return int(text.split("#", 1)[0].strip())
        except ValueError:
            return 1

    def roll_coins(self, text):
        text_lower = text.lower().strip()
        escolha = "cara" if "cara" in text_lower else "coroa"
        valor_alvo = 2 if escolha == "cara" else 1
        repeticoes = self._get_repetitions(text_lower)

        output = []
        sucessos = 0

        for _ in range(repeticoes):
            roll_val = random.randint(1, 2)
            is_sucesso = roll_val == valor_alvo

            if is_sucesso:
                sucessos += 1

            nome_face = "Cara" if roll_val == 2 else "Coroa"
            cor_fundo = "#22c55e" if is_sucesso else "#ef4444"
            cor_texto = "#000" if is_sucesso else "#fff"

            caixa_resultado = (
                f"<span class='result-box' style='margin-right: 8px; background-color: {cor_fundo};"
                f" color: {cor_texto}; border: 1px solid {cor_fundo};'>{nome_face}</span>"
            )
            visual = f"1d2 ⟵ Alvo: {escolha.capitalize()}"
            output.append(f"<div style='display: block; margin-bottom: 10px;'>{caixa_resultado} ⟵ {visual}</div>")

        if repeticoes == 3:
            if sucessos >= 2:
                status = "<span style='color: #4ade80;'>SUCESSO! 🛡️ (Aparou o golpe)</span>"
                borda_painel = "#22c55e"
            else:
                status = "<span style='color: #ef4444;'>FALHA! ❌ (Tomou o dano)</span>"
                borda_painel = "#ef4444"

            painel_parry = f"""
            <div style="margin-top: 10px; padding: 12px; background: #1e1e1e; border-radius: 6px; border: 1px solid {borda_painel}; width: fit-content; font-size: 16px;">
                <strong>Teste de Parry:</strong> {sucessos}/3 acertos ⟵ {status}
            </div>
            """
            output.append(painel_parry)
        elif repeticoes > 1:
            painel_acertos = f"""
            <div style="margin-top: 10px; padding: 10px; background: #1e1e1e; border-radius: 6px; border: 1px solid #444; width: fit-content;">
                <strong>Acertos Totais:</strong> {sucessos}/{repeticoes}
            </div>
            """
            output.append(painel_acertos)

        return "".join(output)

    def parse_expression(self, expression):
        expression = expression.strip()

        if expression.lower().startswith("r"):
            expression = expression[1:].strip()

        math_expr = ""
        visual_expr = ""
        last_end = 0

        for match in self.dice_pattern.finditer(expression):
            start, end = match.span()
            raw_text = match.group(0)

            intermediario = expression[last_end:start]
            math_expr += intermediario
            visual_expr += intermediario

            n_str, faces_str, drop_str, math_op = match.groups()
            n = int(n_str) if n_str else 1
            faces = int(faces_str)
            drop = int(drop_str) if drop_str else 0

            rolls = [random.randint(1, faces) for _ in range(n)]
            rolls.sort(reverse=True)

            total = 0
            fmt_rolls = []

            for i, r in enumerate(rolls):
                is_dropped = (0 < drop < n) and (i >= n - drop)

                classes = []
                if is_dropped:
                    classes.append("dropped")
                if r == faces:
                    classes.append("crit-success")
                elif r == 1:
                    classes.append("crit-fail")

                if classes:
                    class_str = " ".join(classes)
                    fmt_rolls.append(f"<span class='{class_str}'>{r}</span>")
                else:
                    fmt_rolls.append(str(r))

                if not is_dropped:
                    total += r

            rolls_str = f"[{', '.join(fmt_rolls)}]"

            unit_math = str(total) + (math_op.replace("/", "//") if math_op else "")
            try:
                unit_final = eval(unit_math)
                if isinstance(unit_final, float):
                    unit_final = int(unit_final)
            except Exception:
                unit_final = total

            math_expr += str(unit_final)

            if n == 1:
                visual_expr += f"[{fmt_rolls[0]}] {raw_text}"
            else:
                visual_expr += f"[{unit_final}] = {rolls_str} {raw_text}"

            last_end = end

        tail = expression[last_end:]
        math_tail = ""
        comentario = ""

        for i, char in enumerate(tail):
            if char not in self.allowed_chars:
                math_tail = tail[:i]
                comentario_raw = tail[i:]

                while math_tail and math_tail[-1] in "+-*/(). ":
                    comentario_raw = math_tail[-1] + comentario_raw
                    math_tail = math_tail[:-1]

                comentario = comentario_raw.strip()
                break
        else:
            math_tail = tail

        math_expr += math_tail
        visual_expr += math_tail

        if not all(c in self.allowed_chars for c in math_expr.replace(" ", "")):
            return "Erro de sintaxe", visual_expr, comentario

        try:
            safe_expr = math_expr.replace("/", "//")
            final_result = eval(safe_expr, {"__builtins__": None}, {})
            if isinstance(final_result, float):
                final_result = int(final_result)
        except Exception:
            final_result = "Erro Matemático"

        return final_result, visual_expr, comentario

    def roll(self, text):
        if ("cara" in text.lower() or "coroa" in text.lower()) and "d2" in text.lower():
            return self.roll_coins(text)

        repeticoes, base_expr = self._parse_roll_input(text)
        output = []
        soma_total = 0
        teve_erro = False

        for _ in range(repeticoes):
            sub_expressions = base_expr.split(";")
            line_results = []

            for sub_expr in sub_expressions:
                if not sub_expr.strip():
                    continue

                result, visual, comentario = self.parse_expression(sub_expr)
                caixa_resultado = f"<span class='result-box' style='margin-right: 8px;'>{result}</span>"

                if comentario:
                    line_results.append(f"'{comentario}', {caixa_resultado} ⟵ {visual.strip()}")
                else:
                    line_results.append(f"{caixa_resultado} ⟵ {visual.strip()}")

                if isinstance(result, (int, float)):
                    soma_total += result
                else:
                    teve_erro = True

            linha_montada = "<span class='separator'>|</span>".join(line_results)
            output.append(f"<div style='display: block; margin-bottom: 10px;'>{linha_montada}</div>")

        if repeticoes > 1 and not teve_erro:
            botao_soma = f"""
            <details style="margin-top: 5px; cursor: pointer; background: #1e1e1e; padding: 10px; border-radius: 6px; border: 1px solid #444; width: fit-content;">
                <summary style="color: #fff; outline: none; user-select: none;">
                    Somar as {repeticoes} rolagens
                </summary>
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #444; font-size: 16px;">
                    Soma Total: <span class='result-box' style='color: #fff;'>{soma_total}</span>
                </div>
            </details>
            """
            output.append(botao_soma)

        return "".join(output)

    def _parse_roll_input(self, text):
        if "#" not in text:
            return 1, text

        parts = text.split("#", 1)
        try:
            return int(parts[0]), parts[1]
        except ValueError:
            return 1, text


bot = DiceRoller()


@app.route("/")
def home():
    return render_template("index.html")


def get_combat_data(room):
    if room not in room_combats:
        room_combats[room] = {"active": False, "turn_index": 0, "order": []}
    return room_combats[room]


def get_history_data(room):
    if room not in room_histories:
        room_histories[room] = []
    return room_histories[room]


def get_chat_history_data(room):
    if room not in room_text_chats:
        room_text_chats[room] = []
    return room_text_chats[room]


def _normalize_room(room):
    return room.strip().lower()


def _is_gm(room, username):
    current_gm = room_masters.get(room)
    return bool(current_gm and current_gm.lower() == username.lower())


def _trim_history(history, limit):
    if len(history) > limit:
        history.pop(0)


def _emit_player_update(room):
    emit("update_players", list(room_players.get(room, {}).values()), room=room)


def _emit_system_message(room, message):
    emit("system_message", {"msg": message}, room=room)


@socketio.on("join_room")
def handle_join(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "Anônimo").strip()
    want_gm = data.get("is_gm", False)

    if not room or not username:
        return

    current_gm = room_masters.get(room)
    is_gm_assigned = False

    if want_gm:
        if current_gm is None or current_gm.lower() == username.lower():
            room_masters[room] = username
            is_gm_assigned = True
        else:
            emit(
                "join_error",
                {
                    "msg": (
                        f'❌ O mestre "{current_gm}" já está registrado nesta mesa! '
                        "Entre com esse nome para reconectar ou como jogador."
                    )
                },
            )
            return
    elif _is_gm(room, username):
        is_gm_assigned = True

    join_room(room)

    emit(
        "join_success",
        {
            "is_gm": is_gm_assigned,
            "username": username,
            "room": room,
            "chat_locked": room_chat_locked.get(room, False),
        },
    )

    history = get_history_data(room)
    filtered_history = []
    for item in history:
        if "gm_private" in item and is_gm_assigned:
            filtered_history.append(item["gm_private"])
        else:
            filtered_history.append(item["public"])

    emit("load_history", filtered_history)
    emit("load_chat_history", get_chat_history_data(room))
    emit("update_combat", get_combat_data(room))

    titulo = "👑 MESTRE" if is_gm_assigned else "🎲 Jogador"
    _emit_system_message(room, f"🟢 <strong>{username}</strong> ({titulo}) entrou/reconectou na mesa!")

    sid = request.sid
    user_sessions[sid] = {"room": room, "username": username}
    if room not in room_players:
        room_players[room] = {}
    room_players[room][sid] = {"username": username, "is_gm": is_gm_assigned}
    _emit_player_update(room)


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    if sid not in user_sessions:
        return

    room = user_sessions[sid]["room"]
    if room in room_players and sid in room_players[room]:
        del room_players[room][sid]
        if not room_players[room]:
            del room_players[room]
        _emit_player_update(room)

    del user_sessions[sid]


@socketio.on("leave_gm")
def handle_leave_gm(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "").strip()
    current_gm = room_masters.get(room)

    if current_gm and current_gm.lower() == username.lower():
        del room_masters[room]
        _emit_system_message(room, f'👑 O mestre <strong>{username}</strong> liberou o posto de Mestre da sala.')
        emit("gm_status_changed", {"is_gm": False})

        for player_data in room_players.get(room, {}).values():
            if player_data["username"] == username:
                player_data["is_gm"] = False
        _emit_player_update(room)


@socketio.on("leave_room")
def handle_leave_room(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "").strip()
    sid = request.sid

    if not room or not username:
        return

    session = user_sessions.get(sid)
    if not session or session.get("room", "").lower() != room:
        return

    leave_room(room)
    _emit_system_message(room, f'🚪 <strong>{username}</strong> saiu da sala atual.')

    if room in room_players and sid in room_players[room]:
        del room_players[room][sid]
        if not room_players[room]:
            del room_players[room]
        _emit_player_update(room)

    if sid in user_sessions:
        del user_sessions[sid]


@socketio.on("clear_chat")
def handle_clear_chat(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "").strip()
    current_gm = room_masters.get(room)

    if current_gm and current_gm.lower() == username.lower():
        room_histories[room] = []
        room_text_chats[room] = []
        emit("chat_cleared", {"msg": "🗑️ O mestre limpou o histórico do chat."}, room=room)


@socketio.on("toggle_chat_lock")
def handle_toggle_chat_lock(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "").strip()
    current_gm = room_masters.get(room)

    if current_gm and current_gm.lower() == username.lower():
        current_state = room_chat_locked.get(room, False)
        new_state = not current_state
        room_chat_locked[room] = new_state

        status_str = "bloqueado 🔒" if new_state else "desbloqueado 🔓"
        emit(
            "chat_lock_updated",
            {"locked": new_state, "msg": f"O chat foi {status_str} pelo mestre."},
            room=room,
        )


@socketio.on("send_text_chat")
def handle_send_text_chat(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "Anônimo").strip()
    message = data.get("message", "").strip()

    if not room or not message:
        return

    if room_chat_locked.get(room, False) and not _is_gm(room, username):
        emit(
            "system_message",
            {"msg": "❌ O chat está bloqueado pelo mestre. Você não pode enviar mensagens agora."},
            room=request.sid,
        )
        return

    history = get_chat_history_data(room)
    history.append({"username": username, "message": message})
    _trim_history(history, CHAT_HISTORY_LIMIT)

    emit("receive_text_chat", {"username": username, "message": message}, room=room)


@socketio.on("update_combat_state")
def handle_combat_update(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "").strip()

    if not _is_gm(room, username):
        return

    combat = get_combat_data(room)
    action = data.get("action")

    if action == "toggle_combat":
        combat["active"] = not combat["active"]
        combat["turn_index"] = 0
        status_str = "iniciado! ⚔️" if combat["active"] else "encerrado. 🕊️"
        _emit_system_message(room, f"🚨 <strong>Combate {status_str}</strong>")
    elif action == "add_combatant":
        nome = data.get("name", "").strip()
        init_val = int(data.get("init", 0))

        if nome:
            combat["order"].append({"name": nome, "init": init_val})
            combat["order"].sort(key=lambda item: item["init"], reverse=True)
    elif action == "remove_combatant":
        idx = data.get("index", -1)
        if 0 <= idx < len(combat["order"]):
            combat["order"].pop(idx)
            if combat["turn_index"] >= len(combat["order"]):
                combat["turn_index"] = 0
    elif action == "next_turn":
        if combat["order"]:
            combat["turn_index"] = (combat["turn_index"] + 1) % len(combat["order"])
            atual = combat["order"][combat["turn_index"]]
            _emit_system_message(room, f"⏱️ É a vez de <strong>{atual['name']}</strong>!")

    emit("update_combat", combat, room=room)


@socketio.on("send_roll")
def handle_roll(data):
    room = _normalize_room(data.get("room", ""))
    username = data.get("username", "Anônimo").strip()
    expressao = data.get("expressao", "").strip()
    is_oculto = data.get("is_oculto", False)

    if not expressao or not room:
        return

    if room_chat_locked.get(room, False) and not _is_gm(room, username):
        emit(
            "system_message",
            {"msg": "❌ O chat está bloqueado pelo mestre. Você não pode rolar agora."},
            room=request.sid,
        )
        return

    if is_oculto and not _is_gm(room, username):
        is_oculto = False

    resultado_html = bot.roll(expressao)
    history = get_history_data(room)

    if is_oculto:
        gm_msg = {
            "username": f"👑 {username} (Rolagem Oculta)",
            "html": resultado_html,
            "is_oculto": True,
        }
        public_msg = {
            "username": f"👑 {username}",
            "html": '<div style="color: #c084fc; font-style: italic;">[Rolou os dados em segredo...]</div>',
            "is_oculto": True,
        }

        history.append({"public": public_msg, "gm_private": gm_msg})
        emit("receive_roll", gm_msg, room=request.sid)
        emit("receive_roll", public_msg, room=room, include_self=False)
    else:
        prefixo = "👑 " if _is_gm(room, username) else ""
        msg = {"username": f"{prefixo}{username}", "html": resultado_html, "is_oculto": False}
        history.append({"public": msg})
        emit("receive_roll", msg, room=room)

    _trim_history(history, ROOM_HISTORY_LIMIT)


if __name__ == "__main__":
    socketio.run(app, debug=True)