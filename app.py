from flask import Flask, render_template, request, jsonify
import re
import random

app = Flask(__name__)

class DiceRoller:
    def __init__(self):
        self.dice_pattern = re.compile(r'(?i)(\d*)d(\d+)(?:dl(\d+))?((?:[*/]\s*\d+(?:\.\d+)?)*)')
        self.allowed_chars = set("0123456789+-*/(). ")

    def parse_expression(self, expression):
        expression = expression.strip()
        
        # IDEIA 2: Se começar com 'r' ou 'R', removemos a letra para a matemática funcionar pura
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
        soma_total = 0
        teve_erro = False

        for _ in range(repeticoes):
            sub_expressions = base_expr.split(';')
            line_results = []
            
            for sub_expr in sub_expressions:
                if not sub_expr.strip(): continue
                result, visual = self.parse_expression(sub_expr)
                
                caixa_resultado = f"<span class='result-box'> {result} </span>"
                line_results.append(f"{caixa_resultado} ⟵ {visual.strip()}")

                # Acumula o valor para a soma total (se não for uma mensagem de erro)
                if isinstance(result, (int, float)):
                    soma_total += result
                else:
                    teve_erro = True
            
            linha_montada = "<span class='separator'>|</span>".join(line_results)
            output.append(f"<div style='display: block; margin-bottom: 10px;'>{linha_montada}</div>")
            
        # IDEIA 1: Se jogou mais de 1 dado, cria o botão de Soma Total
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

@app.route('/roll', methods=['POST'])
def process_roll():
    dados = request.get_json()
    expressao = dados.get('expressao', '')
    
    resultado_html = bot.roll(expressao)
    
    return jsonify({'html': resultado_html})

if __name__ == '__main__':
    app.run(debug=True) 