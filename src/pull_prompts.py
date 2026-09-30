"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull do prompt semente do desafio
3. Salva localmente em prompts/bug_to_user_story_v1.yml

DICAS DE IMPLEMENTAÇÃO:

- O pull é feito pelo cliente do LangSmith:

      from langsmith import Client
      client = Client()
      prompt = client.pull_prompt(
          "leonanluppi/bug_to_user_story_v1",
          dangerously_pull_public_prompt=True,
      )

- O parâmetro `dangerously_pull_public_prompt=True` é obrigatório sempre que o
  identificador tem dono explícito ("owner/nome"). O LangSmith bloqueia esse pull
  por padrão porque um prompt do Hub é um objeto LangChain serializado, que pode
  vir de terceiros. Aqui o prompt é o do desafio, então o risco é conhecido.

- O retorno é um ChatPromptTemplate. Para extrair o conteúdo das mensagens,
  use a serialização nativa do LangChain (`prompt.messages`, e o atributo
  `.prompt.template` de cada mensagem).

- Use `save_yaml` de utils.py para gravar o resultado no arquivo .yml.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from utils import save_yaml, check_env_vars, print_section_header

load_dotenv()

# Prompt semente de BAIXA QUALIDADE publicado no Hub pelo repositório base.
SOURCE_PROMPT = "leonanluppi/bug_to_user_story_v1"

# Onde o pull é gravado localmente.
OUTPUT_PATH = "prompts/bug_to_user_story_v1.yml"

# Nome da chave que o YAML deve expor como raiz (mesmo do arquivo original).
PROMPT_KEY = "bug_to_user_story_v1"


def _message_to_role(message) -> str:
    """
    Descobre se uma mensagem do ChatPromptTemplate é de sistema ou de usuário.

    O LangChain 1.x serializa cada mensagem como um objeto com `.pretty_repr`
    e uma classe específica (SystemMessagePromptTemplate, HumanMessagePromptTemplate,
    ...). Preferimos a classe e caímos para `type`/`role` como fallback para
    continuar funcionando se a serialização mudar.
    """
    class_name = type(message).__name__.lower()

    if "system" in class_name:
        return "system"
    if "human" in class_name or "user" in class_name:
        return "user"
    if "ai" in class_name or "assistant" in class_name:
        return "assistant"

    # Fallback: o objeto pode carregar `type` ou `role`.
    for attr in ("type", "role"):
        value = getattr(message, attr, None)
        if isinstance(value, str) and value:
            value = value.lower()
            if "system" in value:
                return "system"
            if "human" in value or "user" in value:
                return "user"
            if "ai" in value or "assistant" in value:
                return "assistant"

    return "unknown"


def _extract_template(message) -> str:
    """
    Extrai o texto do template de uma mensagem do ChatPromptTemplate.

    Tenta os atributos na ordem em que normalmente estão disponíveis:
    `.prompt.template` (StringPromptTemplate dentro da mensagem) e,
    como fallback, `.content` / `.template` / `str(message)`.
    """
    prompt_attr = getattr(message, "prompt", None)
    if prompt_attr is not None:
        template = getattr(prompt_attr, "template", None)
        if isinstance(template, str):
            return template

    for attr in ("content", "template"):
        value = getattr(message, attr, None)
        if isinstance(value, str):
            return value

    return str(message)


def prompt_to_dict(prompt, prompt_key: str = PROMPT_KEY) -> dict:
    """
    Converte um ChatPromptTemplate vindo do Hub no dicionário que vai pro YAML.

    O schema do arquivo local é o mesmo usado pelo projeto:

        bug_to_user_story_v1:
          description: ...
          system_prompt: |
            ...
          user_prompt: |
            ...
          version: "v1"
          tags: [...]
    """
    description = ""
    system_prompt = ""
    user_prompt = ""

    # Metadados que o LangSmith anexa ao objeto (quando existem).
    metadata = getattr(prompt, "metadata", None) or {}
    if isinstance(metadata, dict):
        description = metadata.get("description", "") or ""

    for message in getattr(prompt, "messages", []) or []:
        role = _message_to_role(message)
        text = _extract_template(message)

        if role == "system" and not system_prompt:
            system_prompt = text
        elif role == "user" and not user_prompt:
            user_prompt = text
        elif not system_prompt:
            # Se o Hub devolver uma única mensagem sem marcação clara de papel,
            # tratamos como o system prompt (é o caso do prompt semente v1).
            system_prompt = text

    if not description:
        description = f"Prompt importado do LangSmith Hub: {SOURCE_PROMPT}"

    # Variáveis detectadas, apenas para documentar no YAML.
    variables = sorted(getattr(prompt, "input_variables", []) or [])

    return {
        prompt_key: {
            "description": description,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "version": "v1",
            "source": SOURCE_PROMPT,
            "input_variables": variables,
            "tags": ["bug-analysis", "user-story", "product-management"],
        }
    }


def pull_prompts_from_langsmith():
    """
    Faz o pull do prompt semente do LangSmith Prompt Hub.

    Returns:
        O ChatPromptTemplate baixado, ou None em caso de falha.
    """
    print(f"🔽 Fazendo pull do prompt: {SOURCE_PROMPT}")

    client = Client()

    try:
        # `dangerously_pull_public_prompt=True` é obrigatório para identificadores
        # com dono explícito ("owner/nome"): o prompt do Hub é um objeto LangChain
        # serializado, potencialmente de terceiros. Aqui é o prompt semente do
        # desafio, então o risco é conhecido e aceito.
        prompt = client.pull_prompt(
            SOURCE_PROMPT,
            dangerously_pull_public_prompt=True,
        )
    except Exception as e:
        print(f"\n❌ ERRO ao fazer pull de '{SOURCE_PROMPT}': {e}")
        print("\nVerifique:")
        print("- LANGSMITH_API_KEY está correta no .env")
        print("- O prompt 'leonanluppi/bug_to_user_story_v1' ainda existe no Hub")
        print("- Sua conexão com a internet está funcionando")
        return None

    print("   ✓ Prompt baixado com sucesso")
    return prompt


def main():
    """Função principal"""
    print_section_header("PULL DE PROMPTS DO LANGSMITH HUB")

    if not check_env_vars(["LANGSMITH_API_KEY", "LANGSMITH_PROJECT"]):
        return 1

    prompt = pull_prompts_from_langsmith()
    if prompt is None:
        return 1

    data = prompt_to_dict(prompt)

    output_path = Path(OUTPUT_PATH)
    if not save_yaml(data, str(output_path)):
        return 1

    system_prompt = data[PROMPT_KEY]["system_prompt"]
    user_prompt = data[PROMPT_KEY]["user_prompt"]

    print(f"   ✓ Salvo em: {output_path}")
    print(f"   ✓ Variáveis de entrada: {data[PROMPT_KEY]['input_variables']}")

    print("\n📄 Conteúdo capturado:")
    print(f"   system_prompt: {len(system_prompt)} caracteres")
    print(f"   user_prompt:   {len(user_prompt)} caracteres")

    # Diagnóstico explícito dos defeitos do prompt v1 — útil para justificar
    # a refatoração documentada no README.
    problems = []
    if "{bug_report}" in system_prompt and "{bug_report}" in user_prompt:
        problems.append("{bug_report} duplicado no system prompt e no user prompt")
    if "Você é um" not in system_prompt and "Você é uma" not in system_prompt:
        problems.append("sem persona/papel bem definido")
    if system_prompt.count("Exemplo") == 0 and "exemplo" not in system_prompt.lower():
        problems.append("sem exemplos few-shot")
    if "passo a passo" not in system_prompt.lower():
        problems.append("sem instrução de raciocínio (CoT)")
    if "critérios de aceitação" not in system_prompt.lower():
        problems.append("não exige critérios de aceitação")

    if problems:
        print("\n⚠️  Problemas detectados no prompt v1:")
        for p in problems:
            print(f"   - {p}")

    print("\n✅ Pull concluído. Agora otimize o prompt em prompts/bug_to_user_story_v2.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
