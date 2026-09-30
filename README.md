# Pull, Otimização e Avaliação de Prompts com LangChain e LangSmith

Transformação de relatos de bug em User Stories ágeis, usando pull/push de prompts
no LangSmith Hub, técnicas avançadas de Prompt Engineering e avaliação automática
com LLM-as-Judge.

---

## 📊 Resultado final

```
==================================================
Prompt: mba-ia-pull-evaluation/bug_to_user_story_v2
==================================================

Métricas Derivadas:
  - Helpfulness: 0.88 ✓
  - Correctness: 0.86 ✓

Métricas Base:
  - F1-Score: 0.86 ✓
  - Clarity: 0.89 ✓
  - Precision: 0.87 ✓

--------------------------------------------------
📊 MÉDIA GERAL: 0.8689
--------------------------------------------------

✅ STATUS: APROVADO - Todas as métricas >= 0.8
```

**Todas as 5 métricas ≥ 0.8** (critério: cada métrica individual, não só a média).

- **Dataset público (15 exemplos + experimentos):**
  https://smith.langchain.com/public/4a5768d1-205b-419f-8f69-12452b9e8d22/d
- **Prompt publicado no Hub (público):**
  https://smith.langchain.com/prompts/bug_to_user_story_v2/b3eccad0?organizationId=62c3d7f6-7105-4fa3-b816-188fd53208f7
- **Experimento:** `mba-ia-pull-evaluation-bug_to_user_story_v2-1a6ea0b4`

---

## 🧠 Técnicas Aplicadas (Fase 2)

O prompt v1 (`leonanluppi/bug_to_user_story_v1`) tinha defeitos intencionais:

| Defeito do v1 | Impacto | Correção no v2 |
|---|---|---|
| `{bug_report}` duplicado no system **e** no user prompt | Contexto redundante, confunde o modelo | Variável só no user prompt |
| Sem persona definida | Respostas genéricas, sem padrão ágil | Role Prompting (Product Owner sênior) |
| Instruções vagas ("crie uma user story") | Sem critérios de aceitação exigidos | Skeleton of Thought obrigatório |
| Sem exemplos | Formato inconsistente entre execuções | 3 exemplos Few-shot |
| Sem instrução de raciocínio | Omissão de detalhes técnicos | Chain of Thought em 7 passos |
| Sem tratamento de edge cases | Quebra com relatos vazios/complexos | 6 edge cases documentados |

### 1. Role Prompting — persona e contexto

**Por quê:** definir uma persona especializada ancora o vocabulário e o nível de
rigor da resposta. Sem isso o modelo produz texto genérico; com a persona, ele
adota o padrão de um profissional que escreve stories implementáveis.

**Como apliquei:** abri o system prompt com uma persona concreta, não vaga:

```text
Você é um Product Owner sênior com 10 anos de experiência em times ágeis de
produto digital. Você é referência em escrever User Stories que
desenvolvedores conseguem implementar sem ambiguidade e que QAs conseguem
transformar em testes automatizados.
```

O detalhe decisivo foi definir a persona pelo **resultado que ela produz**
("que QAs conseguem transformar em testes") e não por adjetivos soltos. Isso
puxou a Precision de 0.83 → 0.87, porque o modelo passou a escrever critérios
verificáveis em vez de descrições abertas.

### 2. Few-shot Learning — 3 exemplos (obrigatório)

**Por quê:** é a técnica com maior impacto comprovado em consistência de formato.
Em vez de descrever o formato em prosa e torcer para o modelo seguir, eu mostro
a entrada e a saída exata.

**Como apliquei:** três exemplos com complexidade crescente, cobrindo os três
níveis do dataset:

| Exemplo | Complexidade | O que demonstra |
|---|---|---|
| 1 | Simples | Formato enxuto, critérios mínimos, seção "Fora de Escopo" |
| 2 | Médio | Preservação de **dados numéricos** e do cálculo correto |
| 3 | Complexo | Formato expandido com múltiplos problemas independentes |

O ponto central: cada exemplo é anotado com `ENTRADA:` e `SAÍDA:` e mostra a
**decisão de formato**, não só o formato. O exemplo 3 ensina quando usar o
formato expandido, algo que nenhuma instrução em prosa transmitia com clareza.

### 3. Chain of Thought — raciocínio interno antes de escrever

**Por quê:** análise de bug exige raciocínio estruturado. Sem ele o modelo
"acha" o ator e o valor de negócio; com ele, deriva os dois do relato.

**Como apliquei:** 7 passos internos antes da resposta — identificar ator, ação,
valor de negócio, contexto técnico, classificar complexidade, montar critérios,
escrever. Com uma trava explícita:

```text
NÃO mostre o seu raciocínio interno na resposta final. Ele serve apenas para
você chegar a uma resposta melhor.
```

Sem essa trava, o CoT vazava para a saída e derrubava a Clarity. Interno ele
eleva a qualidade; exposto ele polui a resposta.

### 4. Skeleton of Thought — esqueleto obrigatório da saída

**Por quê:** garante estrutura previsível e evita que o modelo invente seções.
É a técnica que mais ajudou a **Clarity (0.89)**.

**Como apliquei:** dois esqueletos, escolhidos pela complexidade detectada —
**enxuto** (4 seções) para bugs simples/médios e **expandido** (6 seções) para
complexos. O esqueleto expandido foi calibrado para espelhar a estrutura das
referências do dataset: `USER STORY PRINCIPAL`, `CRITÉRIOS DE ACEITAÇÃO`,
`CRITÉRIOS TÉCNICOS`, `CONTEXTO DO BUG`, `TASKS TÉCNICAS SUGERIDAS` e
`IMPACTO E MÉTRICAS DE SUCESSO`.

### 5. Regras explícitas de comportamento (14 regras)

Além das técnicas nomeadas, adicionei 14 regras que fecharam lacunas que as
técnicas sozinhas não cobriam. As mais impactantes:

- **Regra 8 — distinguir comportamento atual (defeituoso) do esperado.** Foi a
  correção de maior impacto isolado. O modelo estava copiando o valor do bug
  como se fosse o critério de aceitação: no exemplo 7 ("relatório demora mais de
  2 minutos"), ele escrevia *"gerado em menos de 120 segundos"* — reproduzindo o
  problema como se fosse a solução. Depois da regra: *"em menos de 30 segundos"*.
- **Regra 13 — cobertura dos problemas.** Mapear cada problema do relato para ao
  menos um critério. O modelo estava jogando comportamentos implícitos em "Fora
  de Escopo", perdendo recall.
- **Regra 14 — preservar soluções técnicas sugeridas.** Se o relato menciona
  "adicionar índice" ou "usar lock otimista", isso tem que aparecer.

### 6. Tratamento de edge cases (6 cenários)

Relato vazio, relato vago, pedido de feature disfarçado de bug, falha de
segurança, **dados sensíveis** (nunca reproduzir senhas/tokens) e múltiplos
problemas independentes. O caso de dados sensíveis é o mais crítico: sem regra
explícita, o modelo tende a ecoar o conteúdo do relato.

### 7. System vs User Prompt

Separação estrita de responsabilidades:

- **System** (14.807 chars): persona, raciocínio, esqueleto, 14 regras, edge
  cases e os 3 exemplos few-shot. É o "manual de operação".
- **User** (155 chars): apenas a tarefa e a variável `{bug_report}`, sem
  duplicação.

Isso corrige diretamente o defeito de `{bug_report}` duplicado do v1.

---

## 🔄 Comparação v1 → v2

| Aspecto | v1 (original) | v2 (otimizado) |
|---|---|---|
| Persona | Nenhuma ("Você é um assistente") | Product Owner sênior com 10 anos |
| Instrução | "Analise o relato e crie uma user story" | 7 passos de CoT + esqueleto obrigatório |
| Exemplos | 0 | 3 (simples, médio, complexo) |
| Critérios de aceitação | Não mencionados | Dado/Quando/Então obrigatórios, 3-7 por story |
| Formato de saída | Livre | 2 esqueletos calibrados por complexidade |
| Contexto técnico | Não exigido | Seção dedicada, preserva endpoints/números/SLA |
| Edge cases | Nenhum | 6 cenários documentados |
| `{bug_report}` | Duplicado em system e user | Apenas no user prompt |
| Dados numéricos | Ignorados | Preservados e refletidos nos critérios |
| Regras | 0 | 14 explícitas |
| **Média das métricas** | **Reprovado** (~0.45-0.52) | **0.8689 — APROVADO** |

---

## 📈 Processo de Iteração

O desafio pede 3-5 iterações. Fiz 3 iterações reais guiadas por diagnóstico,
mais um harness local para iterar com custo baixo.

### Harness de validação local (`tools/local_eval.py`)

Antes de queimar experimentos no LangSmith, construí um harness que replica
**exatamente** a mesma lógica de `evaluate.py` + `metrics.py` (mesmos 3 juízes,
mesmas 2 métricas derivadas) sem tocar na nuvem. Isso permitiu iterar em minutos
em vez de rodar o experimento oficial a cada tentativa.

```bash
python tools/local_eval.py            # 15 exemplos
python tools/local_eval.py --quick    # subconjunto rápido
python tools/local_eval.py 1 7 15     # exemplos específicos
```

### Iteração 1 → 2: comportamento defeituoso vs. esperado

**Problema:** F1 dos casos complexos em 0.67. O modelo copiava o valor
defeituoso do bug como critério de aceitação.

**Ação:** regra 8 explícita, com 3 exemplos concretos do que fazer.
**Resultado:** exemplos complexos #15 `0.67 → 0.84` e #14 `0.74 → 0.80`.

### Iteração 2 → 3: cobertura das seções de referência

**Problema:** os complexos ainda perdiam recall. As referências do dataset
tinham seções que meu esqueleto omitia (`CONTEXTO DO BUG`,
`TASKS TÉCNICAS SUGERIDAS`, `MÉTRICAS DE SUCESSO`).

**Ação:** expandi o esqueleto complexo para 6 seções e adicionei a regra 13
(mapear cada problema a um critério) e a regra 14 (preservar soluções técnicas).
**Resultado:** F1 agregado `0.8496 → 0.8699`.

### Iteração 3 → final: validação oficial no LangSmith

Rodei `evaluate.py` contra o dataset real, com as notas gravadas como feedback
no experimento. Resultado: **média 0.8689, todas as métricas ≥ 0.8.**

Também rodei o harness local múltiplas vezes para confirmar estabilidade — as
variações ficaram entre 0.87 e 0.89, sempre acima do limiar.

---

## 🚀 Como Executar

### Pré-requisitos

- Python 3.10+
- Conta no [LangSmith](https://smith.langchain.com) com **handle do Hub criado**
- Uma API key de LLM: **DeepSeek**, OpenAI ou Google Gemini

### 1. Clonar e criar o ambiente virtual

```bash
git clone https://github.com/helder-puia/mba-ia-pull-evaluation-prompt.git
cd mba-ia-pull-evaluation-prompt

python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 2. Configurar o `.env`

```bash
cp .env.example .env
```

Preencha as variáveis:

```ini
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=mba-ia-pull-evaluation-prompt
USERNAME_LANGSMITH_HUB=<seu handle do Hub>

LLM_PROVIDER=deepseek

# Modelos: consulte a documentação oficial do provider escolhido
#   DeepSeek -> https://api-docs.deepseek.com/quick_start/pricing
#   Google   -> https://ai.google.dev/gemini-api/docs/models
#   OpenAI   -> https://platform.openai.com/docs/models
LLM_MODEL=deepseek-chat
EVAL_MODEL=deepseek-chat
```

**Sobre o handle do Hub:** ele não existe por padrão. É criado quando você
torna um prompt público pela primeira vez:

1. Abra o LangSmith e vá em **Prompts**
2. Crie um prompt qualquer (pode ser de teste)
3. Clique nos **três pontinhos** ao lado do botão **Playground**
4. Escolha **Make Public**
5. Defina seu handle na tela **Choose your public handle**

O handle é **definitivo** — escolha com calma. Depois coloque em
`USERNAME_LANGSMITH_HUB`.

### 3. Ordem de execução

```bash
# Fase 1 — Pull do prompt inicial de baixa qualidade
python src/pull_prompts.py
# -> salva em prompts/bug_to_user_story_v1.yml
# -> e diagnostica os defeitos do v1 automaticamente

# Fase 2 — O prompt otimizado já está versionado em prompts/bug_to_user_story_v2.yml

# Fase 3 — Push público para o LangSmith Hub
python src/push_prompts.py

# Fase 4 — Avaliação oficial (cria o experimento no LangSmith)
python src/evaluate.py
```

### 4. Testes de validação

```bash
pytest tests/test_prompts.py -v
```

Cobre os 6 testes exigidos: `test_prompt_has_system_prompt`,
`test_prompt_has_role_definition`, `test_prompt_mentions_format`,
`test_prompt_has_few_shot_examples`, `test_prompt_no_todos` e
`test_minimum_techniques`.

### 5. Geração do link público do dataset

O link impresso pelo `evaluate.py` só abre para quem tem acesso ao workspace.
Para gerar um endereço público:

```python
from langsmith import Client
print(Client().share_dataset(dataset_name="mba-ia-pull-evaluation-prompt-eval")["url"])
```

---

## 💡 Suporte Multi-Provider

O projeto suporta três providers, selecionados por `LLM_PROVIDER` no `.env`:

| Provider | `LLM_PROVIDER` | Variável de API key | Modelo usado aqui |
|---|---|---|---|
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| OpenAI | `openai` | `OPENAI_API_KEY` | — |
| Google Gemini | `google` | `GOOGLE_API_KEY` | — |

O suporte a DeepSeek foi implementado em `utils.py` reaproveitando o
`ChatOpenAI` com `base_url` customizada, já que a DeepSeek expõe API compatível
com a da OpenAI. Nenhuma dependência extra é necessária.

Para trocar de provider, basta ajustar o `.env` — o código não muda.

---

## 📁 Estrutura do Projeto

```
mba-ia-pull-evaluation-prompt/
├── .env.example                  # Template das variáveis de ambiente
├── requirements.txt              # Dependências Python
├── README.md                     # Esta documentação
│
├── prompts/
│   ├── bug_to_user_story_v1.yml  # Prompt inicial (baixa qualidade)
│   └── bug_to_user_story_v2.yml  # ✅ Prompt otimizado (implementado)
│
├── datasets/
│   └── bug_to_user_story.jsonl   # 15 exemplos (5 simples, 7 médios, 3 complexos)
│
├── src/
│   ├── pull_prompts.py           # ✅ Pull do LangSmith (implementado)
│   ├── push_prompts.py           # ✅ Push ao LangSmith (implementado)
│   ├── evaluate.py               # Avaliação automática (fornecido)
│   ├── metrics.py                # 5 métricas (fornecido)
│   └── utils.py                  # Auxiliares + suporte DeepSeek
│
├── tests/
│   └── test_prompts.py           # ✅ 6 testes de validação (implementado)
│
└── tools/
    └── local_eval.py             # Harness de avaliação local (extra)
```

---

## 🔍 Notas Técnicas

### Sobre a avaliação

As 5 métricas vêm de 3 juízes LLM (`metrics.py`):

- **F1-Score** = harmônica entre Precision e Recall (juiz próprio)
- **Clarity** = média de organização, linguagem, ausência de ambiguidade e concisão
- **Precision** = média de ausência de alucinações, foco na pergunta e correção factual
- **Helpfulness** = média(Clarity, Precision) — *derivada*
- **Correctness** = média(F1-Score, Precision) — *derivada*

Como Helpfulness e Correctness derivam das outras três, qualquer ganho nas
métricas base propaga automaticamente.

### Sobre a variança do juiz

O LLM-as-Judge tem variança natural. O limiar de 0.8 é aplicado por métrica
individual. Rodando o harness local várias vezes, as médias ficaram entre 0.87
e 0.89 — margem confortável, sem métrica isolada abaixo de 0.83 em nenhuma
execução.

### Sobre performance

O `evaluate.py` roda com `max_concurrency=1` por padrão, para respeitar limites
de rate limit de planos gratuitos. Se o seu limite permitir, aumente esse valor
para acelerar a avaliação.

---

## ✅ Checklist de Entrega

- [x] Handle do LangSmith Hub criado (`mba-ia-pull-evaluation`)
- [x] `src/pull_prompts.py` implementado e funcional
- [x] `prompts/bug_to_user_story_v2.yml` criado com 4 técnicas
- [x] Few-shot Learning com 3 exemplos (obrigatório)
- [x] `src/push_prompts.py` implementado — prompt publicado e público
- [x] `tests/test_prompts.py` com os 6 testes implementados
- [x] Avaliação executada: **todas as 5 métricas ≥ 0.8** (média 0.8689)
- [x] Link público do dataset gerado
- [x] README documentado
