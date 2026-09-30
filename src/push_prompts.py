"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

DICAS DE IMPLEMENTAÇÃO:

- O push é feito pelo cliente do LangSmith:

      from langsmith import Client
      from langchain_core.prompts import ChatPromptTemplate

      client = Client()
      prompt = ChatPromptTemplate.from_messages([
          ("system", system_prompt),
          ("user", user_prompt),
      ])
      url = client.push_prompt(
          f"{username}/bug_to_user_story_v2",
          object=prompt,
          is_public=True,
          description="...",
          tags=[...],
      )

- `username` vem de USERNAME_LANGSMITH_HUB no .env e precisa ser o seu handle
  do Hub. Se você ainda não tem um handle, veja as instruções no .env.example.

- A variável do template precisa ser {bug_report}, que é a chave de entrada
  usada no dataset de avaliação.

- Use `load_yaml` de utils.py para ler o arquivo .yml.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, check_env_vars, print_section_header

load_dotenv()

# Arquivo local com o prompt otimizado.
PROMPT_FILE = "prompts/bug_to_user_story_v2.yml"

# Chave raiz dentro do YAML.
PROMPT_KEY = "bug_to_user_story_v2"

# Nome do prompt publicado no Hub (sem o handle, que vem do .env).
HUB_PROMPT_NAME = "bug_to_user_story_v2"

# Variável obrigatória do template — precisa casar com a chave de entrada do
# dataset de avaliação.
REQUIRED_INPUT_VARIABLE = "bug_report"


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    errors = []

    if not isinstance(prompt_data, dict):
        return (False, ["O YAML não produziu um dicionário válido"])

    if PROMPT_KEY not in prompt_data:
        return (False, [f"Chave raiz '{PROMPT_KEY}' não encontrada no YAML"])

    data = prompt_data[PROMPT_KEY]

    # Campos obrigatórios
    for field in ("description", "system_prompt", "user_prompt", "version"):
        if field not in data:
            errors.append(f"Campo obrigatório faltando: {field}")

    system_prompt = (data.get("system_prompt") or "").strip()
    user_prompt = (data.get("user_prompt") or "").strip()

    if not system_prompt:
        errors.append("system_prompt está vazio")
    if not user_prompt:
        errors.append("user_prompt está vazio")

    # A variável {bug_report} precisa existir e estar disponível para o template.
    if REQUIRED_INPUT_VARIABLE not in system_prompt and REQUIRED_INPUT_VARIABLE not in user_prompt:
        errors.append(
            f"A variável '{{{REQUIRED_INPUT_VARIABLE}}}' não aparece em nenhum dos prompts"
        )

    # Não pode sobrar TODO do esqueleto
    for field_name, value in (("system_prompt", system_prompt), ("user_prompt", user_prompt)):
        if "TODO" in value or "[TODO]" in value:
            errors.append(f"{field_name} ainda contém TODOs")

    # Mínimo de 2 técnicas
    techniques = data.get("techniques_applied", []) or []
    if len(techniques) < 2:
        errors.append(f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}")

    # Few-shot é obrigatório no desafio
    techniques_lower = " ".join(str(t).lower() for t in techniques)
    if "few" not in techniques_lower:
        errors.append("Few-shot Learning é obrigatório e não está em techniques_applied")

    # Precisa ter exemplos no corpo do prompt
    if "ENTRADA:" not in system_prompt or "SAÍDA:" not in system_prompt:
        errors.append(
            "Nenhum exemplo few-shot detectado (esperado marcadores 'ENTRADA:' e 'SAÍDA:')"
        )

    return (len(errors) == 0, errors)


def build_chat_prompt(data: dict) -> ChatPromptTemplate:
    """Monta o ChatPromptTemplate a partir dos campos do YAML."""
    return ChatPromptTemplate.from_messages([
        ("system", data["system_prompt"]),
        ("user", data["user_prompt"]),
    ])


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    client = Client()

    data = prompt_data[PROMPT_KEY]
    prompt = build_chat_prompt(data)

    description = data.get("description", "")
    tags = list(data.get("tags", []) or [])

    # Enriquece as tags com as técnicas aplicadas, para ficarem visíveis no Hub.
    for technique in data.get("techniques_applied", []) or []:
        slug = str(technique).strip().lower().replace(" ", "-")
        if slug and slug not in tags:
            tags.append(slug)

    print(f"🚀 Fazendo push: {prompt_name}")
    print(f"   Descrição: {description[:100]}...")
    print(f"   Tags: {tags}")
    print(f"   Variáveis: {prompt.input_variables}")

    try:
        url = client.push_prompt(
            prompt_name,
            object=prompt,
            is_public=True,
            description=description,
            tags=tags,
        )
    except Exception as e:
        print(f"\n❌ ERRO ao fazer push de '{prompt_name}': {e}")
        print("\nVerifique:")
        print("- LANGSMITH_API_KEY está correta no .env")
        print("- USERNAME_LANGSMITH_HUB é o seu handle público do Hub")
        print("- Você já criou um handle (via 'Make Public' em qualquer prompt)")
        return False

    print(f"   ✓ Push concluído com sucesso")
    print(f"   ✓ URL: {url}")
    return True


def main():
    """Função principal"""
    print_section_header("PUSH DE PROMPTS OTIMIZADOS AO LANGSMITH HUB")

    required_vars = ["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]
    if not check_env_vars(required_vars):
        print("\n💡 Para criar seu handle do Hub:")
        print("   1. Abra o LangSmith e vá em Prompts")
        print("   2. Crie um prompt qualquer ou abra um existente")
        print("   3. Clique nos três pontinhos ao lado do botão Playground")
        print("   4. Escolha 'Make Public'")
        print("   5. Defina seu handle e coloque-o em USERNAME_LANGSMITH_HUB no .env")
        return 1

    username = os.getenv("USERNAME_LANGSMITH_HUB", "").strip()

    if not Path(PROMPT_FILE).exists():
        print(f"❌ Arquivo não encontrado: {PROMPT_FILE}")
        print("\nCrie o arquivo prompts/bug_to_user_story_v2.yml antes de continuar.")
        return 1

    print(f"📂 Carregando: {PROMPT_FILE}")
    prompt_data = load_yaml(PROMPT_FILE)

    if prompt_data is None:
        return 1

    print("🔍 Validando prompt...")
    is_valid, errors = validate_prompt(prompt_data)

    if not is_valid:
        print("\n❌ Validação falhou:")
        for error in errors:
            print(f"   - {error}")
        print("\nCorrija os erros acima antes de fazer o push.")
        return 1

    print("   ✓ Validação OK")

    data = prompt_data[PROMPT_KEY]
    techniques = data.get("techniques_applied", [])
    print(f"   ✓ Técnicas: {techniques}")
    print(f"   ✓ system_prompt: {len(data['system_prompt'])} caracteres")
    print(f"   ✓ user_prompt:   {len(data['user_prompt'])} caracteres")

    prompt_name = f"{username}/{HUB_PROMPT_NAME}"

    if not push_prompt_to_langsmith(prompt_name, prompt_data):
        return 1

    print("\n" + "=" * 50)
    print("RESUMO")
    print("=" * 50)
    print(f"✓ Prompt publicado: {prompt_name}")
    print(f"✓ Público: sim")
    print(f"\nPróximo passo: python src/evaluate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
