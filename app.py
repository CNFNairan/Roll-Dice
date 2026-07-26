from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import re
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_rpg_123'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- MEMÓRIA RAM POR SALA ---
room_masters = {}    # { "sala": "nome_do_mestre" }
room_combats = {}    # { "sala": { "active": False, "turn_index": 0, "order": [...] } }
room_histories = {}  # { "sala": [ { "public": ..., "gm_private": ... } ] }
room_chat_locked = {} # NOVO: { "sala": True/False } para travar chat

user_sessions = {}   # { sid: {"room": room, "username": username} }
room_players = {}    # { "sala": { sid: {"username": username, "is_gm": bool} } }

class DiceRoller:
    def __init__(self):
        self.dice_pattern = re.compile(r'(?i)(\d*)d(\d+)(?:dl(\d+))?((?:[*/]\s*\d+(?:\.\d+)?)*)')
        self.allowed_chars = set("0123456789+-*/(). ")

    def roll_coins(self, text):
        text_lower = text.lower().strip()
        escolha = 'cara' if 'cara' in text_lower else 'coroa'
        valor_alvo = 2 if escolha == 'cara' else 1

        repeticoes = 1
        if '#' in text_lower:
            try:
                repeticoes = int(text_lower.split('#')[0].strip())
            except ValueError:
                repeticoes = 1

        output = []
        sucessos = 0
        
        for _ in range(repeticoes):
            roll_val = random.randint(1, 2)
            is_sucesso = (roll_val == valor_alvo)
            
            if is_sucesso:
                sucessos += 1
                
            nome_face = "Cara" if roll_val == 2 else "Coroa"
            cor_fundo = "#22c55e" if is_sucesso else "#ef4444"
            cor_texto = "#000" if is_sucesso else "#fff"
            
            caixa_resultado = f"<span class='result-box' style='margin-right: 8px; background-color: {cor_fundo}; color: {cor_texto}; border: 1px solid {cor_fundo};'>{nome_face}</span>"
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
        
        if expression.lower().startswith('r'):
            expression = expression[1:].strip()
            
        math_expr = ""
        visual_expr = ""
        last_end = 0
        
        matches = list(self.dice_pattern.finditer(expression))
        
        for match in matches:
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
            
            unit_math = str(total) + (math_op.replace('/', '//') if math_op else "")
            try:
                unit_final = eval(unit_math)
                if isinstance(unit_final, float):
                    unit_final = int(unit_final)
            except Exception:
                unit_final = total
            
            math_expr += str(unit_final)
            
            if n == 1:
                visual_expr += f"[{unit_final}] {raw_text}"
            else:
                visual_expr += f"[{unit_final}] = {rolls_str} {raw_text}"
                
            last_end = end
            
        # --- LÓGICA DE EXTRAÇÃO DE COMENTÁRIO ---
        tail = expression[last_end:]
        math_tail = ""
        comentario = ""

        # Lê a sobra da expressão para identificar onde o comentário de texto começa
        for i, char in enumerate(tail):
            if char not in self.allowed_chars:
                math_tail = tail[:i]
                comentario_raw = tail[i:]
                
                # Joga operadores órfãos (+, -) que possam ter ficado no final para o comentário
                while math_tail and math_tail[-1] in "+-*/(). ":
                    comentario_raw = math_tail[-1] + comentario_raw
                    math_tail = math_tail[:-1]
                
                comentario = comentario_raw.strip()
                break
        else:
            math_tail = tail
            
        math_expr += math_tail
        visual_expr += math_tail
        
        if not all(c in self.allowed_chars for c in math_expr.replace(' ', '')):
            return "Erro de sintaxe", visual_expr, comentario
            
        try:
            safe_expr = math_expr.replace('/', '//')
            final_result = eval(safe_expr, {"__builtins__": None}, {})
            if isinstance(final_result, float):
                final_result = int(final_result)
        except Exception:
            final_result = "Erro Matemático"
            
        return final_result, visual_expr, comentario

    def roll(self, text):
        if ('cara' in text.lower() or 'coroa' in text.lower()) and 'd2' in text.lower():
            return self.roll_coins(text)

        if '#' in text:
            parts = text.split('#', 1)
            try:
                repeticoes = int(parts[0])
                base_expr = parts[1]
            except ValueError:
                repeticoes = 1
                base_expr = text
        else:
            repeticoes = 1
            base_expr = text

        output = []
        soma_total = 0
        teve_erro = False

        for _ in range(repeticoes):
            sub_expressions = base_expr.split(';')
            line_results = []
            
            for sub_expr in sub_expressions:
                if not sub_expr.strip(): continue
                
                # Agora o parse_expression retorna 3 valores (Resultado, Visual, Comentário)
                result, visual, comentario = self.parse_expression(sub_expr)
                
                caixa_resultado = f"<span class='result-box' style='margin-right: 8px;'>{result}</span>"
                
                # Se tiver um comentário, aplica o visual desejado: 'investigação', 3 ⟵ [1] 1d6 + 2
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
                <summary style="color: #4ade80; font-weight: bold; outline: none; user-select: none;">
                    Somar as {repeticoes} rolagens
                </summary>
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #444; font-size: 16px;">
                    Soma Total: <span class='result-box' style='background-color: #22c55e; color: #000;'>{soma_total}</span>
                </div>
            </details>
            """
            output.append(botao_soma)
            
        return "".join(output)

bot = DiceRoller()

@app.route('/')
def home():
    return render_template('index.html')

def get_combat_data(room):
    if room not in room_combats:
        room_combats[room] = {"active": False, "turn_index": 0, "order": []}
    return room_combats[room]

def get_history_data(room):
    if room not in room_histories:
        room_histories[room] = []
    return room_histories[room]

# --- EVENTOS DE CONEXÃO & HISTÓRICO ---

@socketio.on('join_room')
def handle_join(data):
    room = data.get('room', '').strip().lower()
    username = data.get('username', 'Anônimo').strip()
    want_gm = data.get('is_gm', False)

    if not room or not username:
        return

    current_gm = room_masters.get(room)
    is_gm_assigned = False

    if want_gm:
        if current_gm is None or current_gm.lower() == username.lower():
            room_masters[room] = username
            is_gm_assigned = True
        else:
            emit('join_error', {'msg': f'❌ O mestre "{current_gm}" já está registrado nesta mesa! Entre com esse nome para reconectar ou como jogador.'})
            return
    else:
        if current_gm and current_gm.lower() == username.lower():
            is_gm_assigned = True

    join_room(room)
    
    emit('join_success', {
        'is_gm': is_gm_assigned,
        'username': username,
        'room': room,
        'chat_locked': room_chat_locked.get(room, False) # NOVO: Envia estado do chat
    })

    # RESTAURA HISTÓRICO DE ROLAGENS (Pós-F5)
    history = get_history_data(room)
    filtered_history = []
    for item in history:
        if 'gm_private' in item and is_gm_assigned:
            filtered_history.append(item['gm_private'])
        else:
            filtered_history.append(item['public'])
            
    emit('load_history', filtered_history)

    # RESTAURA ESTADO DE COMBATE
    emit('update_combat', get_combat_data(room))

    titulo = "👑 MESTRE" if is_gm_assigned else "🎲 Jogador"
    emit('system_message', {
        'msg': f"🟢 <strong>{username}</strong> ({titulo}) entrou/reconectou na mesa!"
    }, room=room)

    sid = request.sid
    user_sessions[sid] = {'room': room, 'username': username}
    if room not in room_players:
        room_players[room] = {}
    room_players[room][sid] = {'username': username, 'is_gm': is_gm_assigned}
    emit('update_players', list(room_players[room].values()), room=room)


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in user_sessions:
        room = user_sessions[sid]['room']
        if room in room_players and sid in room_players[room]:
            del room_players[room][sid]
            emit('update_players', list(room_players[room].values()), room=room)
        del user_sessions[sid]


@socketio.on('leave_gm')
def handle_leave_gm(data):
    room = data.get('room', '').strip().lower()
    username = data.get('username', '').strip()
    current_gm = room_masters.get(room)
    
    if current_gm and current_gm.lower() == username.lower():
        del room_masters[room]
        emit('system_message', {'msg': f'👑 O mestre <strong>{username}</strong> liberou o posto de Mestre da sala.'}, room=room)
        emit('gm_status_changed', {'is_gm': False})

        for sid, p_data in room_players.get(room, {}).items():
            if p_data['username'] == username:
                p_data['is_gm'] = False
        emit('update_players', list(room_players.get(room, {}).values()), room=room)

# --- NOVOS EVENTOS DE CHAT (LIMPAR E TRAVAR) ---

@socketio.on('clear_chat')
def handle_clear_chat(data):
    room = data.get('room', '').strip().lower()
    username = data.get('username', '').strip()
    current_gm = room_masters.get(room)

    # Verifica se quem pediu foi realmente o mestre daquela sala
    if current_gm and current_gm.lower() == username.lower():
        room_histories[room] = [] # Limpa a memória
        emit('chat_cleared', {'msg': '🗑️ O mestre limpou o histórico do chat.'}, room=room)

@socketio.on('toggle_chat_lock')
def handle_toggle_chat_lock(data):
    room = data.get('room', '').strip().lower()
    username = data.get('username', '').strip()
    current_gm = room_masters.get(room)

    # Verifica se quem pediu foi realmente o mestre
    if current_gm and current_gm.lower() == username.lower():
        current_state = room_chat_locked.get(room, False)
        new_state = not current_state
        room_chat_locked[room] = new_state
        
        status_str = "bloqueado 🔒" if new_state else "desbloqueado 🔓"
        emit('chat_lock_updated', {
            'locked': new_state, 
            'msg': f'O chat foi {status_str} pelo mestre.'
        }, room=room)

# --- EVENTOS DE ORDEM DE AÇÃO (COMBATE) ---

@socketio.on('update_combat_state')
def handle_combat_update(data):
    room = data.get('room', '').strip().lower()
    username = data.get('username', '').strip()
    current_gm = room_masters.get(room)

    if not current_gm or current_gm.lower() != username.lower():
        return

    combat = get_combat_data(room)
    action = data.get('action')

    if action == 'toggle_combat':
        combat['active'] = not combat['active']
        combat['turn_index'] = 0
        status_str = "iniciado! ⚔️" if combat['active'] else "encerrado. 🕊️"
        emit('system_message', {'msg': f"🚨 <strong>Combate {status_str}</strong>"}, room=room)

    elif action == 'add_combatant':
        nome = data.get('name', '').strip()
        init_val = int(data.get('init', 0))
        
        if nome:
            combat['order'].append({
                'name': nome,
                'init': init_val
            })
            combat['order'].sort(key=lambda x: x['init'], reverse=True)

    elif action == 'remove_combatant':
        idx = data.get('index', -1)
        if 0 <= idx < len(combat['order']):
            combat['order'].pop(idx)
            if combat['turn_index'] >= len(combat['order']):
                combat['turn_index'] = 0

    elif action == 'next_turn':
        if combat['order']:
            combat['turn_index'] = (combat['turn_index'] + 1) % len(combat['order'])
            atual = combat['order'][combat['turn_index']]
            emit('system_message', {'msg': f"⏱️ É a vez de <strong>{atual['name']}</strong>!"}, room=room)

    emit('update_combat', combat, room=room)

# --- EVENTO DE ROLAGEM ---

@socketio.on('send_roll')
def handle_roll(data):
    room = data.get('room', '').strip().lower()
    username = data.get('username', 'Anônimo').strip()
    expressao = data.get('expressao', '').strip()
    is_oculto = data.get('is_oculto', False)

    if not expressao or not room:
        return

    current_gm = room_masters.get(room)
    is_real_gm = (current_gm and current_gm.lower() == username.lower())

    # NOVO: Bloqueia rolagem se o chat estiver travado e o usuário não for o Mestre
    if room_chat_locked.get(room, False) and not is_real_gm:
        emit('system_message', {'msg': '❌ O chat está bloqueado pelo mestre. Você não pode rolar agora.'}, room=request.sid)
        return

    if is_oculto and not is_real_gm:
        is_oculto = False

    resultado_html = bot.roll(expressao)
    history = get_history_data(room)

    if is_oculto:
        gm_msg = {
            'username': f"👑 {username} (Rolagem Oculta)",
            'html': resultado_html,
            'is_oculto': True
        }
        public_msg = {
            'username': f"👑 {username}",
            'html': '<div style="color: #c084fc; font-style: italic;">[Rolou os dados em segredo...]</div>',
            'is_oculto': True
        }

        history.append({'public': public_msg, 'gm_private': gm_msg})

        emit('receive_roll', gm_msg, room=request.sid)
        emit('receive_roll', public_msg, room=room, include_self=False)
    else:
        prefixo = "👑 " if is_real_gm else ""
        msg = {
            'username': f"{prefixo}{username}",
            'html': resultado_html,
            'is_oculto': False
        }

        history.append({'public': msg})
        emit('receive_roll', msg, room=room)

    if len(history) > 50:
        history.pop(0)

if __name__ == '__main__':
    socketio.run(app, debug=True)