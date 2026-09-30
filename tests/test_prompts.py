"""
Testes automatizados para validação de prompts.
"""
import pytest
import yaml
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import validate_prompt_structure

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"


def load_prompts(file_path: str):
    """Carrega prompts do arquivo YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def prompts():
    """Carrega o YAML de prompts otimizados uma vez por módulo."""
    assert PROMPT_FILE.exists(), f"Arquivo de prompt não encontrado: {PROMPT_FILE}"
    data = load_prompts(str(PROMPT_FILE))
    assert isinstance(data, dict), "O YAML não produziu um dicionário"
    return data


@pytest.fixture(scope="module")
def prompt_data(prompts):
    """Retorna o bloco interno do prompt otimizado (v2)."""
    assert PROMPT_KEY in prompts, f"Chave raiz '{PROMPT_KEY}' não encontrada no YAML"
    return prompts[PROMPT_KEY]


@pytest.fixture(scope="module")
def full_prompt_text(prompt_data):
    """Texto completo do prompt (system + user), usado nas buscas por conteúdo."""
    return "\n".join([
        str(prompt_data.get("system_prompt", "")),
        str(prompt_data.get("user_prompt", "")),
    ])


class TestPrompts:
    def test_prompt_has_system_prompt(self, prompt_data):
        """Verifica se o campo 'system_prompt' existe e não está vazio."""
        assert "system_prompt" in prompt_data, "Campo 'system_prompt' ausente no YAML"

        system_prompt = prompt_data["system_prompt"]
        assert system_prompt is not None, "'system_prompt' é None"
        assert isinstance(system_prompt, str), "'system_prompt' não é uma string"
        assert system_prompt.strip(), "'system_prompt' está vazio"

        # O user_prompt também precisa existir e conter a variável de entrada.
        assert isinstance(prompt_data.get("user_prompt", ""), str)
        assert prompt_data["user_prompt"].strip(), "'user_prompt' está vazio"

    def test_prompt_has_role_definition(self, prompt_data):
        """Verifica se o prompt define uma persona (ex: "Você é um Product Manager")."""
        system_prompt = prompt_data.get("system_prompt", "")

        # A persona deve ser declarada explicitamente no system prompt.
        assert "Você é" in system_prompt, (
            "Persona não definida: esperado algo como 'Você é um Product Owner...'"
        )

        # E deve nomear o papel concreto.
        persona_terms = ["Product Owner", "Product Manager", "product owner", "product manager"]
        assert any(term in system_prompt for term in persona_terms), (
            f"Papel não nomeado explicitamente. Esperado um de: {persona_terms}"
        )

    def test_prompt_mentions_format(self, prompt_data):
        """Verifica se o prompt exige formato Markdown ou User Story padrão."""
        full_text = "\n".join([
            str(prompt_data.get("system_prompt", "")),
            str(prompt_data.get("user_prompt", "")),
        ])

        assert "Markdown" in full_text or "markdown" in full_text, (
            "O prompt não exige formato Markdown"
        )

        # O padrão ágil de User Story deve estar exigido.
        assert "Como um" in full_text and "eu quero" in full_text and "para que" in full_text, (
            "O prompt não exige o formato padrão 'Como um... eu quero... para que...'"
        )

        # E os critérios de aceitação em Dado/Quando/Então.
        assert "Dado que" in full_text, "Critérios de aceitação 'Dado que' não exigidos"
        assert "Quando" in full_text, "Critérios de aceitação 'Quando' não exigidos"
        assert "Então" in full_text, "Critérios de aceitação 'Então' não exigidos"

    def test_prompt_has_few_shot_examples(self, prompt_data):
        """Verifica se o prompt contém exemplos de entrada/saída (técnica Few-shot)."""
        system_prompt = prompt_data.get("system_prompt", "")

        # Marcadores explícitos de exemplo.
        assert "ENTRADA:" in system_prompt, "Nenhum exemplo few-shot: falta marcador 'ENTRADA:'"
        assert "SAÍDA:" in system_prompt, "Nenhum exemplo few-shot: falta marcador 'SAÍDA:'"

        # Precisa de pelo menos 2 exemplos, conforme exigido pelo desafio.
        num_examples = system_prompt.count("ENTRADA:")
        assert num_examples >= 2, (
            f"Few-shot exige ao menos 2 exemplos, encontrados: {num_examples}"
        )

        assert system_prompt.count("SAÍDA:") >= 2, (
            "Cada exemplo few-shot precisa de uma SAÍDA correspondente"
        )

        # A técnica deve estar declarada nos metadados.
        techniques = " ".join(str(t).lower() for t in prompt_data.get("techniques_applied", []))
        assert "few" in techniques, "'Few-shot' não listado em techniques_applied"

    def test_prompt_no_todos(self, prompt_data):
        """Garante que você não esqueceu nenhum `[TODO]` no texto."""
        system_prompt = str(prompt_data.get("system_prompt", ""))
        user_prompt = str(prompt_data.get("user_prompt", ""))

        assert "[TODO]" not in system_prompt, "system_prompt ainda contém '[TODO]'"
        assert "[TODO]" not in user_prompt, "user_prompt ainda contém '[TODO]'"

        # Marcadores do esqueleto que nunca devem sobrar. Note que a busca é
        # case-sensitive pelos marcadores em maiúsculas entre colchetes: a
        # palavra portuguesa "todo" (ex: "todo critério") não é um TODO pendente
        # e não deve reprovar o teste.
        for marker in ("[TODO]", "[FIXME]", "[XXX]"):
            assert marker not in system_prompt, f"system_prompt ainda contém '{marker}'"
            assert marker not in user_prompt, f"user_prompt ainda contém '{marker}'"

        # A estrutura geral precisa passar na validação de utils.py.
        is_valid, errors = validate_prompt_structure(prompt_data)
        assert is_valid, f"validate_prompt_structure falhou: {errors}"

    def test_minimum_techniques(self, prompt_data):
        """Verifica (através dos metadados do yaml) se pelo menos 2 técnicas foram listadas."""
        techniques = prompt_data.get("techniques_applied")

        assert techniques is not None, "'techniques_applied' ausente nos metadados do YAML"
        assert isinstance(techniques, list), "'techniques_applied' deve ser uma lista"
        assert len(techniques) >= 2, (
            f"Mínimo de 2 técnicas requeridas, encontradas: {len(techniques)}"
        )

        # Todas as entradas precisam ser strings não vazias.
        for technique in techniques:
            assert isinstance(technique, str) and technique.strip(), (
                f"Técnica inválida nos metadados: {technique!r}"
            )

        # Few-shot é obrigatório pelo enunciado.
        techniques_lower = " ".join(t.lower() for t in techniques)
        assert "few" in techniques_lower, "Few-shot Learning é obrigatório e não foi listado"

        # A variável de entrada esperada pelo dataset deve estar no prompt.
        assert "bug_report" in prompt_data.get("system_prompt", "") or \
               "bug_report" in prompt_data.get("user_prompt", ""), (
            "A variável '{bug_report}' não aparece em nenhum dos prompts"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
