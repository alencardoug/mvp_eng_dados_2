"""As amostras de registros para o portal (D95, ADR-0058 e as três retificações).

Dois níveis. Sem banco: a máscara, a ordem e a varredura, com as contraprovas da revisão do plano
(RVPR-3-02): um vazamento deliberado reprova, uma coincidência curta legítima passa, JSON escapado é
achado, e o deslocado do `support_agents` linha 2 aparece como está. Com o arquivo e o armazém **na mesma
invocação** (o `make amostras-check`, logo depois do `make amostras`): a cobertura, a máscara por
ocorrência contra as linhas sem máscara, com o esperado calculado aqui e não no exportador, e a varredura
dos valores pessoais fortes. Em outra invocação, pula: a amostra é do *build* que cita.
"""

from __future__ import annotations

import decimal
import json
import re

import pytest

from mvp_ed1.models import amostras as a

M = a.MARCADOR

#: Um pacote mínimo, com uma relação bruta do legado, o *staging* dela e a quarentena.
PACOTE = {
    "relations": {
        "raw_legacy.support_agents": {"columns": {
            "legacy_row_id": {"sensitivity": "internal"}, "agent_code": {"sensitivity": "internal"},
            "first_name": {"sensitivity": "personal"}, "email": {"sensitivity": "personal"},
            "team": {"sensitivity": "public"}}, "primary_key": []},
        "staging.stg_legacy__support_agents": {"columns": {
            "legacy_row_id": {"sensitivity": "internal"}, "agent_code": {"sensitivity": "internal"},
            "first_name": {"sensitivity": "personal"}, "original_payload": {"sensitivity": "personal"},
            "achados": {"sensitivity": "internal"}}, "primary_key": []},
        "quarantine.rejected_legacy_records": {"columns": {
            "source_table": {"sensitivity": "internal"}, "findings": {"sensitivity": "personal"},
            "original_payload": {"sensitivity": "personal"}}, "primary_key": []},
        "trusted.legacy_presence_by_capture": {"columns": {
            "source_table": {"sensitivity": "internal"}, "payloads": {"sensitivity": "personal"}}, "primary_key": []},
        "analytics.dim_x": {"columns": {"k": {"sensitivity": "internal"}}, "primary_key": ["k"]},
        "consumption.v": {"columns": {"a": {}, "b": {}, "c": {}}, "primary_key": []},
    },
    "view_rules": {"consumption.v": {"columns": {"a": {"role": "grain"}, "b": {"role": "reference"},
                                                 "c": {"role": "identity"}}}},
}


# ── A máscara ────────────────────────────────────────────────────────────────


def test_coluna_pessoal_vira_marcador_e_o_nulo_continua_nulo():
    linha = {"legacy_row_id": 1, "agent_code": "AGT-0001", "first_name": "Ana", "email": None, "team": "X"}
    assert a.mascarar("raw_legacy.support_agents", list(linha), linha, PACOTE) == [1, "AGT-0001", M, None, "X"]


def test_o_deslocado_pelo_defeito_aparece_como_esta():
    """Decisão do Owner (19/11/2026): o `TEXT_DELIMITER` mostra o defeito, com o nome que ele absorveu."""
    linha = {"legacy_row_id": 2, "agent_code": "AGT-0002;Renan;Costela", "first_name": None, "email": "x@example.com",
             "team": "X"}
    assert a.mascarar("raw_legacy.support_agents", list(linha), linha, PACOTE) == [
        2, "AGT-0002;Renan;Costela", None, M, "X"]


def test_o_payload_mantem_a_forma_e_mascara_as_folhas_pessoais():
    payload = {"legacy_row_id": "1", "agent_code": "AGT-0001", "first_name": "Ana", "email": "a@example.com",
               "team": None}
    linha = {"legacy_row_id": 1, "agent_code": "AGT-0001", "first_name": "Ana", "original_payload": payload,
             "achados": {"email": "EMAIL_MALFORMED"}}
    saida = dict(zip(linha, a.mascarar("staging.stg_legacy__support_agents", list(linha), linha, PACOTE)))
    assert saida["original_payload"] == {"legacy_row_id": "1", "agent_code": "AGT-0001", "first_name": M,
                                         "email": M, "team": None}
    assert saida["achados"] == {"email": "EMAIL_MALFORMED"}


def test_chave_desconhecida_no_payload_e_mascarada():
    linha = {"source_table": "support_agents", "original_payload": {"telefone_novo": "+55 (11) 91234-5678"},
             "findings": None}
    saida = dict(zip(linha, a.mascarar("quarantine.rejected_legacy_records", list(linha), linha, PACOTE)))
    assert saida["original_payload"] == {"telefone_novo": M}


@pytest.mark.parametrize("linha", [
    {"source_table": None, "original_payload": {"email": "a@example.com"}, "findings": None},
    {"source_table": "tabela_que_nao_existe", "original_payload": {"email": "a@example.com"}, "findings": None},
    {"source_table": "support_agents", "original_payload": ["forma", "inesperada"], "findings": None},
], ids=["sem-origem", "origem-fora-do-pacote", "forma-inesperada"])
def test_origem_ou_forma_nao_resolvida_vira_marcador_inteiro(linha):
    saida = dict(zip(linha, a.mascarar("quarantine.rejected_legacy_records", list(linha), linha, PACOTE)))
    assert saida["original_payload"] == M


def test_o_achado_de_coluna_pessoal_perde_os_valores_e_o_de_publica_fica():
    findings = [
        {"code": "EMAIL_MALFORMED", "column": "email", "original_value": "a@@example.com", "cleaned_value": None},
        {"code": "TEXT_TRUNCATED", "column": "team", "original_value": "Devol", "cleaned_value": "Devol"},
    ]
    linha = {"source_table": "support_agents", "findings": findings, "original_payload": None}
    saida = dict(zip(linha, a.mascarar("quarantine.rejected_legacy_records", list(linha), linha, PACOTE)))
    assert saida["findings"][0]["original_value"] == M and saida["findings"][0]["cleaned_value"] is None
    assert saida["findings"][1] == findings[1]


def test_a_ultima_captura_do_removido_e_colecao_linha_a_linha():
    """RVPB1-1-01: `last_payload` é coleção de linhas (`legacy_removed_records`), e não objeto; o esperado é
    literal, e não outro algoritmo: a folha pública fica, a pessoal some, o elemento sem forma vira marcador."""
    pacote = {"relations": {**PACOTE["relations"], "trusted.legacy_removed_records": {"columns": {
        "source_table": {"sensitivity": "internal"}, "last_payload": {"sensitivity": "personal"}}, "primary_key": []}}}
    linha = {"source_table": "support_agents",
             "last_payload": [{"email": "ana@example.com", "agent_code": "AGT-0001"}, "solto"]}
    saida = dict(zip(linha, a.mascarar("trusted.legacy_removed_records", list(linha), linha, pacote)))
    assert saida["last_payload"] == [{"email": M, "agent_code": "AGT-0001"}, M]


def test_a_colecao_de_linhas_e_mascarada_linha_a_linha():
    linha = {"source_table": "support_agents", "payloads": [{"email": "a@example.com", "team": "X"}, "solto"]}
    saida = dict(zip(linha, a.mascarar("trusted.legacy_presence_by_capture", list(linha), linha, PACOTE)))
    assert saida["payloads"] == [{"email": M, "team": "X"}, M]


# ── A ordem ──────────────────────────────────────────────────────────────────


def test_a_chave_segue_a_ordem_de_resolucao():
    assert a.chave("analytics.dim_x", PACOTE, {}, ["k"]) == ["k"]
    assert a.chave("consumption.v", PACOTE, {}, ["a", "b", "c"]) == ["a", "c"]
    assert a.chave("raw_legacy.support_agents", PACOTE, {"raw_legacy.support_agents": [["team", "agent_code"],
                                                                                       ["legacy_row_id"]]},
                   ["team"]) == ["legacy_row_id"]
    assert a.chave("raw_legacy.support_agents", PACOTE, {}, ["x", "y"]) == ["x", "y"]


def test_a_prioridade_vale_so_na_lista_fechada():
    """Segunda e terceira retificações do ADR-0058."""
    com = ["raw_legacy.support_agents", "staging.stg_legacy__support_agents", "trusted.legacy_records",
           "trusted.legacy_classifications", "trusted.legacy_eligible_records"]
    sem = ["trusted.legado__customers", "trusted.legacy_presence_by_capture", "trusted.customers",
           "quarantine.rejected_legacy_records", "snapshots.customers_snapshot", "analytics.dim_customer"]
    assert all(a.prioridade(r) for r in com)
    assert not any(a.prioridade(r) for r in sem)


def test_as_unicidades_saem_do_manifest():
    manifest = {
        "sources": {"source.p.legacy.support_agents": {"resource_type": "source", "schema": "raw_legacy",
                                                        "identifier": "support_agents", "name": "support_agents"}},
        "nodes": {"test.p.u": {"resource_type": "test", "attached_node": None,
                               "depends_on": {"nodes": ["source.p.legacy.support_agents"]},
                               "test_metadata": {"name": "unique_combination_of_columns",
                                                 "kwargs": {"combination_of_columns": ["snapshot_id", "legacy_row_id"]}}}},
    }
    assert a.unicidades(manifest) == {"raw_legacy.support_agents": [["snapshot_id", "legacy_row_id"]]}


def test_o_dinheiro_sai_exato():
    assert a.serializavel(decimal.Decimal("12.345678")) == "12.345678"


# ── A varredura dos valores fortes ───────────────────────────────────────────

#: Os formatos que só o campo pessoal tem no gerador: e-mail, documento com `-SIN` e telefone `+55`.
#: Rua e cidade coincidem com texto público legítimo e ficam fora, de propósito.
_FORTE = re.compile(r"(@)|(-SIN$)|(^\+55 )")
#: O nome completo (ADR-0058): de coluna pessoal cujo nome termina em `name`, com ao menos duas palavras.
_NOME_COMPLETO = re.compile(r"^\w{2,}( \w+)+$")


def fortes(valores, nomes=()) -> set[str]:
    saida = {v for v in valores if isinstance(v, str) and _FORTE.search(v)}
    return saida | {v for v in nomes if isinstance(v, str) and len(v) >= 8 and _NOME_COMPLETO.match(v)}


def deslocados_do_manifesto() -> set[str]:
    """As exceções autorizadas (Owner, 19/11/2026): o valor legado inteiro de cada `TEXT_DELIMITER` do manifesto."""
    raiz = a.ROOT / "data" / "legacy"
    saida: set[str] = set()
    for arquivo in sorted(raiz.glob("manifesto-*.json")):
        pilha = [json.loads(arquivo.read_text(encoding="utf-8"))]
        while pilha:
            x = pilha.pop()
            if isinstance(x, dict):
                if x.get("codigo") == "TEXT_DELIMITER" and isinstance(x.get("valor_legado"), str):
                    saida.add(x["valor_legado"])
                pilha.extend(x.values())
            elif isinstance(x, list):
                pilha.extend(x)
    return saida


def vazamentos(arquivo: dict, valores_fortes: set[str], deslocados: set[str] = frozenset()) -> list[str]:
    """Os valores fortes que aparecem no arquivo serializado fora das ocorrências autorizadas.

    A exceção não é o valor, e sim a ocorrência: cada valor legado deslocado pelo `TEXT_DELIMITER`, tirado do
    manifesto, é apagado do texto **inteiro e exato** antes da busca. O mesmo valor em outro lugar continua achado.
    """
    texto = json.dumps(arquivo, ensure_ascii=False)
    for d in sorted(deslocados, key=len, reverse=True):
        for forma in (json.dumps(d, ensure_ascii=False),):
            texto = texto.replace(forma, '""')

    def formas(v: str) -> list[str]:
        # O valor cru e escapado uma, duas e três vezes: JSON dentro de texto dentro do arquivo.
        saida = [v]
        for _ in range(3):
            saida.append(json.dumps(saida[-1], ensure_ascii=False)[1:-1])
        return saida

    return sorted(v for v in valores_fortes if any(f in texto for f in formas(v)))


def test_a_varredura_acha_o_vazamento_deliberado():
    arquivo = {"relations": {"r": {"rows": [["x", {"nota": "contato: ana@example.com"}]]}}}
    assert vazamentos(arquivo, fortes(["ana@example.com"])) == ["ana@example.com"]


def test_a_varredura_acha_o_valor_escapado_em_json():
    escapado = 'a"b@example.com'
    arquivo = {"relations": {"r": {"rows": [[json.dumps({"email": escapado})]]}}}
    assert vazamentos(arquivo, fortes([escapado])) == [escapado]


def test_o_ponto_e_virgula_nao_autoriza_o_vazamento():
    """RVPB1-1-02: só o valor legado exato do manifesto é exceção; um e-mail depois de `;` continua achado."""
    arquivo = {"relations": {"r": {"rows": [["prefixo;ana@example.com", "AGT-0002;Renan;Costela"]]}}}
    assert vazamentos(arquivo, fortes(["ana@example.com"]), {"AGT-0002;Renan;Costela"}) == ["ana@example.com"]


def test_o_deslocado_do_manifesto_e_a_unica_excecao():
    arquivo = {"relations": {"r": {"rows": [["AGT-0002;Renan Costela;x"]]}}}
    assert vazamentos(arquivo, fortes([], nomes=["Renan Costela"]), {"AGT-0002;Renan Costela;x"}) == []
    assert vazamentos(arquivo, fortes([], nomes=["Renan Costela"])) == ["Renan Costela"]


def test_o_nome_completo_e_valor_forte_e_o_curto_nao():
    assert fortes([], nomes=["Ana Maria da Silva", "Ana", "SP"]) == {"Ana Maria da Silva"}


def test_a_coincidencia_curta_legitima_passa():
    """`SP` e `BR` são pessoais no endereço e públicos no armazém: não são valores fortes."""
    arquivo = {"relations": {"r": {"rows": [["SP", "BR", 12]]}}}
    assert vazamentos(arquivo, fortes(["SP", "BR", "12"])) == []


# ── Com o arquivo e o armazém, na mesma invocação ────────────────────────────


@pytest.fixture(scope="module")
def publicado():
    if not a.ARQUIVO.exists():
        pytest.skip(f"{a.ARQUIVO.name} ausente: nasce no `make amostras`, depois da restauração (Bloco 4)")
    return json.loads(a.ARQUIVO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sem_mascara(publicado):
    """As mesmas linhas, na mesma ordem, sem máscara; pula fora da invocação do arquivo."""
    pytest.importorskip("sqlalchemy")
    from mvp_ed1.models.amostras import _em_transacao, carregar_pacote, exportar, procedencia

    pacote = carregar_pacote()
    manifest = json.loads(a.MANIFEST.read_text(encoding="utf-8"))

    def ler(conexao):
        if procedencia(conexao)["invocation_id"] != publicado["provenance"]["invocation_id"]:
            pytest.skip("outra invocação no armazém: a amostra é do build que cita")
        return exportar(conexao, pacote, manifest, publicado["exported_at"],
                        mascara=lambda relacao, colunas, linha, _p: [linha[c] for c in colunas])

    try:
        return pacote, a.serializavel(_em_transacao(ler))
    except a.ExportacaoRecusada as erro:
        pytest.skip(str(erro))


def _esperado(valor_cru, coluna, relacao, linha, pacote):
    """A máscara recalculada aqui, sem o exportador: pessoal → marcador; recipiente → folha a folha."""
    pess = {c for c, m in pacote["relations"][relacao]["columns"].items() if m.get("sensitivity") == "personal"}
    if valor_cru is None or coluna not in pess:
        return valor_cru
    if coluna not in a.RECIPIENTES:
        return M
    nome = relacao.split(".", 1)[1]
    fonte = ("raw_legacy." + nome.removeprefix("stg_legacy__")) if nome.startswith("stg_legacy__") else (
        "raw_legacy." + linha["source_table"] if linha.get("source_table") else None)
    if fonte not in pacote["relations"]:
        return M
    cols = pacote["relations"][fonte]["columns"]
    pess_f = {c for c, m in cols.items() if m.get("sensitivity") == "personal"}

    def folha(obj):
        if not isinstance(obj, dict):
            return M
        return {k: (None if v is None else M if (k in pess_f or k not in cols) else v) for k, v in obj.items()}

    if coluna in ("payloads", "last_payload"):
        return [folha(o) for o in valor_cru] if isinstance(valor_cru, list) else M
    if coluna == "findings":
        if not isinstance(valor_cru, list):
            return M
        saida = []
        for f in valor_cru:
            if not isinstance(f, dict):
                saida.append(M)
                continue
            f = dict(f)
            if f.get("column") in pess_f or f.get("column") not in cols:
                f.update({k: M for k in ("original_value", "cleaned_value") if f.get(k) is not None})
            saida.append(f)
        return saida
    return folha(valor_cru)


@pytest.mark.integracao
def test_a_cobertura_e_o_pacote_da_mesma_publicacao(publicado):
    pacote = a.carregar_pacote()
    assert set(publicado["relations"]) == set(pacote["relations"])
    for r, v in publicado["relations"].items():
        assert v["columns"] == list(pacote["relations"][r]["columns"]), r
        assert len(v["rows"]) == min(a.LINHAS, v["row_count"]), r


@pytest.mark.integracao
def test_a_mascara_por_ocorrencia(publicado, sem_mascara):
    pacote, cru = sem_mascara
    divergentes = []
    for r, v in publicado["relations"].items():
        for i, (linha_pub, linha_cru) in enumerate(zip(v["rows"], cru["relations"][r]["rows"])):
            linha = dict(zip(v["columns"], linha_cru))
            for c, pub, crua in zip(v["columns"], linha_pub, linha_cru):
                if pub != _esperado(crua, c, r, linha, pacote):
                    divergentes.append(f"{r}[{i}].{c}")
    assert divergentes == [], divergentes[:20]


def _mascarados(crua, esperada) -> list:
    """Os valores crus que a máscara esconde: onde o esperado é o marcador, todas as folhas abaixo."""
    if esperada == M:
        pilha, saida = [crua], []
        while pilha:
            x = pilha.pop()
            if isinstance(x, dict):
                pilha.extend(x.values())
            elif isinstance(x, list):
                pilha.extend(x)
            elif x is not None:
                saida.append(x)
        return saida
    if isinstance(crua, dict) and isinstance(esperada, dict):
        return [v for k in crua for v in _mascarados(crua[k], esperada.get(k))]
    if isinstance(crua, list) and isinstance(esperada, list):
        return [v for c, e in zip(crua, esperada) for v in _mascarados(c, e)]
    return []


@pytest.mark.integracao
def test_nenhum_valor_pessoal_forte_aparece_no_arquivo(publicado, sem_mascara):
    """Só os valores que viram marcador: a folha não pessoal de um recipiente pessoal aparece de propósito
    (o documento do fornecedor é `confidential`, e não pessoal)."""
    pacote, cru = sem_mascara
    valores, nomes = set(), set()
    for r, v in cru["relations"].items():
        for linha_crua in v["rows"]:
            linha = dict(zip(v["columns"], linha_crua))
            for c, crua in zip(v["columns"], linha_crua):
                escondidos = _mascarados(crua, _esperado(crua, c, r, linha, pacote))
                valores.update(escondidos)
                if c.endswith("name"):
                    nomes.update(escondidos)
    assert fortes(valores, nomes), "nenhum valor forte mascarado: a varredura passaria vazia"
    assert vazamentos(publicado, fortes(valores, nomes), deslocados_do_manifesto()) == []


def test_a_conferencia_nao_ecoa_ambiente_nem_data_do_arquivo(tmp_path, monkeypatch):
    """RVPB1-1-03: ambiente e data adulterados no cabeçalho aparecem como diferença."""
    cabecalho = {"format": 1, "exported_at": "t", "environment": "local", "as_of_date": "2026-09-01",
                 "masking": {}, "relations": {}, "provenance": {"invocation_id": "i"}}

    def exportar_falso(_c, _p, _m, instante, ambiente, as_of_date, mascara=None):
        return {**cabecalho, "exported_at": instante, "environment": ambiente, "as_of_date": as_of_date}

    monkeypatch.setattr(a, "carregar_pacote", lambda: {})
    monkeypatch.setattr(a, "MANIFEST", tmp_path / "manifest.json")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(a, "procedencia", lambda _c: {"invocation_id": "i"})
    monkeypatch.setattr(a, "exportar", exportar_falso)
    monkeypatch.setattr(a, "_as_of_date", lambda: "2026-09-01")
    monkeypatch.setattr(a, "_em_transacao", lambda fazer: fazer(None))
    arquivo = tmp_path / "amostras.json"
    arquivo.write_text(json.dumps(cabecalho), encoding="utf-8")
    assert a.conferir(arquivo) == []
    arquivo.write_text(json.dumps({**cabecalho, "environment": "gcp", "as_of_date": "1900-01-01"}), encoding="utf-8")
    assert sorted(a.conferir(arquivo)) == ["as_of_date: difere", "environment: difere"]

