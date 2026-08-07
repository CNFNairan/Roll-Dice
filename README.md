# 🎲 RPG Dice Roller - Full-Stack Web Application

![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)
![Render](https://img.shields.io/badge/Render-Deployed-46E3B7?logo=render&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

Uma aplicação web full-stack de **Rolagem de Dados para RPG de Mesa**, desenvolvida para proporcionar aos jogadores uma interface rápida, intuitiva e responsiva durante as sessões de jogo, integrada a um servidor backend em Python e hospedada na nuvem.

🔗 **Acesse o projeto online:** [Dice Roller](https://roll-dice-b06p.onrender.com)

---

## 📌 Sobre o Projeto

Este projeto foi construído para resolver uma necessidade real do meu grupo de RPG: ter um rolador de dados prático, moderno e acessível em qualquer dispositivo (celular ou computador). 

Além da utilidade prática nas sessões, a aplicação foi projetada para demonstrar **domínio no desenvolvimento web full-stack**, unindo um **frontend interativo** (HTML5, CSS3 puro e JavaScript ES6+) a uma **API backend em Python** responsável pela lógica de negócio e processamento de requisições.

---

## 🛠️ Tecnologias Utilizadas

### Frontend
* **HTML5:** Estrutura semântica e acessível.
* **CSS3:** Estilização moderna, layout responsivo (Flexbox/Grid), animações e suporte a temas.
* **JavaScript (ES6+):** Manipulação dinâmica do DOM, gerenciamento de estado das rolagens, consumo de APIs via `fetch` e lógica de interface.

### Backend
* **Python:** Servidor web responsável pelo processamento da lógica de rolagens, validação de modificadores e geração de números aleatórios.
* **HTTP / REST API:** Comunicação assíncrona entre o frontend e a API Python.

### Deploy & Infraestrutura
* **Render:** Hospedagem em nuvem da aplicação e do serviço web em Python.

---

## ✨ Funcionalidades

- 🎲 **Rolagem de Dados Padrão de RPG:** D4, D6, D8, D10, D12, D20, D100.
- 🧮 **Suporte a Modificadores e Múltiplos Dados:** Permite rolar combinações complexas (ex: `2d20 + 5`, `3d6 - 2`).
- 📜 **Histórico de Rolagens em Tempo Real:** Registro detalhado dos últimos resultados, discriminando os dados individuais e o total final.
- 📱 **Design Responsivo & Mobile-First:** Otimizado para ser utilizado no smartphone durante a mesa presencial ou no monitor durante partidas virtuais.
- ⚡ **Comunicação Assíncrona:** Integração fluida entre cliente e servidor com respostas rápidas e sem recarregamento de página.

---

## 📁 Estrutura do Repositório

```text
.
├── static/                   # Arquivos estáticos servidos pelo backend
│   ├── css/
│   │   └── style.css         # Estilização completa e responsiva da aplicação
│   └── js/
│       └── main.js           # Lógica do frontend (DOM, eventos e requisições Fetch)
├── templates/
│   └── index.html            # Interface principal em HTML5
├── app.py                    # Servidor backend em Python e rotas da API
├── requirements.txt          # Dependências do projeto para o deploy
└── README.md                 # Documentação do projeto
