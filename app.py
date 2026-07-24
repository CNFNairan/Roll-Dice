from flask import Flask, render_template, request, jsonify
import re
import random

app = Flask(__name__)

class DiceRoller:
    def __init__(self):
        self.dice_pattern = re.compile(r'(?i)(\d*)d(\d+)(?:dl(\d+))?((?:[*/]\s*\d+(?:\.\d+)?)*)')
        self.allowed_chars = set("0123456789+-*/(). ")

    def parse_expression(self, expression):
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
                    
                # Se tiver classes, envelopa o número no HTML, senão, mostra puro
                if classes:
                    class_str = " ".join(classes)
                    fmt_rolls.append(f"{r}")
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
            
        math_expr += expression[last_end:]
        visual_expr += expression[last_end:]
        
        if not all(c in self.allowed_chars for c in math_expr.replace(' ', '')):
            return "Erro de sintaxe", visual_expr
            
        try:
            safe_expr = math_expr.replace('/', '//')
            final_result = eval(safe_expr, {"__builtins__": None}, {})
            if isinstance(final_result, float):
                final_result = int(final_result)
        except Exception:
            final_result = "Erro Matemático"
            
        return final_result, visual_expr

    def roll(self, text):
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
        for _ in range(repeticoes):
            sub_expressions = base_expr.split(';')
            line_results = []
            
            for sub_expr in sub_expressions:
                if not sub_expr.strip(): continue
                result, visual = self.parse_expression(sub_expr)
                
                # Usa a classe CSS para o fundo da caixa de resultado
                caixa_resultado = f"<span class='result-box'> {result} </span>"
                line_results.append(f"{caixa_resultado} ⟵ {visual.strip()}")
            
            # ATUALIZAÇÃO AQUI: Forçamos o comportamento de bloco e damos 10px de margem embaixo
            linha_montada = "<span class='separator'>|</span>".join(line_results)
            output.append(f"<div style='display: block; margin-bottom: 10px;'>{linha_montada}</div>")
            
        return "".join(output)

# Inicia o robô
bot = DiceRoller()

# Rota principal que carrega a página HTML
@app.route('/')
def home():
    return render_template('index.html')

# Rota API onde o HTML envia o texto e o Python devolve o resultado
@app.route('/roll', methods=['POST'])
def process_roll():
    dados = request.get_json()
    expressao = dados.get('expressao', '')
    
    resultado_html = bot.roll(expressao)
    
    return jsonify({'html': resultado_html})

if __name__ == '__main__':
    app.run(debug=True)