"""As vinte invariantes de negócio do Modelo de Dados §4.

Elas são simultaneamente regra de geração e critério de teste — é o que o
próprio documento diz. Aqui elas são cobradas do conjunto **em memória**, antes
do banco: as que o banco garante por `CHECK` falhariam na carga, mas as que
atravessam linhas precisam também dessa verificação explícita.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

import pytest

from mvp_ed1.generator.dataset import Dataset


def _por(chave: str, linhas: list[dict]) -> dict:
    agrupado = defaultdict(list)
    for linha in linhas:
        agrupado[linha[chave]].append(linha)
    return agrupado


def test_1_item_referencia_pedido_e_sku_existentes(dados: Dataset) -> None:
    pedidos = {p["id"] for p in dados["orders"]}
    variantes = {v["id"] for v in dados["product_variants"]}
    for item in dados["order_items"]:
        assert item["order_id"] in pedidos
        assert item["product_variant_id"] in variantes


def test_2_total_do_pedido_reconcilia(dados: Dataset) -> None:
    itens = _por("order_id", dados["order_items"])
    for pedido in dados["orders"]:
        esperado = (
            pedido["subtotal_amount"]
            - pedido["discount_amount"]
            + pedido["shipping_amount"]
            + pedido["tax_amount"]
        )
        assert pedido["total_amount"] == esperado
        bruto = sum(i["quantity"] * i["unit_price"] for i in itens[pedido["id"]])
        assert abs(pedido["subtotal_amount"] - bruto) <= Decimal("0.02")
        assert pedido["discount_amount"] <= pedido["subtotal_amount"]


def test_3_captura_nunca_excede_a_autorizacao(dados: Dataset) -> None:
    por_pagamento = _por("payment_id", dados["payment_transactions"])
    for transacoes in por_pagamento.values():
        autorizado = sum(
            t["amount"] for t in transacoes
            if t["transaction_type"] == "authorization" and t["result"] == "succeeded"
        )
        capturado = sum(
            t["amount"] for t in transacoes
            if t["transaction_type"] == "capture" and t["result"] == "succeeded"
        )
        assert capturado <= autorizado


def test_4_reembolso_nunca_excede_a_captura(dados: Dataset) -> None:
    capturas = {t["id"]: t for t in dados["payment_transactions"]}
    devolvido: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for reembolso in dados["refunds"]:
        devolvido[reembolso["payment_transaction_id"]] += reembolso["amount"]
    for transacao_id, valor in devolvido.items():
        assert valor <= capturas[transacao_id]["amount"]


def test_5_remessa_nao_envia_mais_do_que_foi_vendido(dados: Dataset) -> None:
    vendido = {i["id"]: i["quantity"] for i in dados["order_items"]}
    enviado: dict[int, int] = defaultdict(int)
    for item in dados["shipment_items"]:
        enviado[item["order_item_id"]] += item["quantity"]
    for item_id, quantidade in enviado.items():
        assert quantidade <= vendido[item_id]


def test_6_recebimento_nao_supera_o_solicitado(dados: Dataset) -> None:
    pedido = {i["id"]: i["quantity_ordered"] for i in dados["purchase_order_items"]}
    recebido: dict[int, int] = defaultdict(int)
    for item in dados["goods_receipt_items"]:
        recebido[item["purchase_order_item_id"]] += item["quantity_received"]
    for item_id, quantidade in recebido.items():
        assert quantidade <= pedido[item_id]


def test_7_todo_movimento_tem_origem_de_negocio(dados: Dataset) -> None:
    for movimento in dados["inventory_movements"]:
        assert movimento["source_type"]
        assert movimento["source_id"]
        assert movimento["quantity_delta"] != 0


def test_8_reserva_encerrada_nao_ocupa_saldo(dados: Dataset) -> None:
    ativo: dict[tuple[int, int], int] = defaultdict(int)
    for reserva in dados["stock_reservations"]:
        if reserva["status"] == "active":
            ativo[(reserva["warehouse_id"], reserva["product_variant_id"])] += reserva["quantity"]
    for saldo in dados["inventory_balances"]:
        chave = (saldo["warehouse_id"], saldo["product_variant_id"])
        assert saldo["quantity_reserved"] <= ativo[chave]
        assert saldo["quantity_reserved"] <= saldo["quantity_on_hand"]


def test_9_transicoes_de_estado_sao_validas(dados: Dataset) -> None:
    from mvp_ed1.generator.domains.vendas import CAMINHOS

    validas = {(None, "pending")}
    for caminho in list(CAMINHOS.values()) + [("pending", "paid", "picking", "cancelled")]:
        validas |= set(zip(caminho, caminho[1:]))
    validas |= {("pending", "cancelled"), ("paid", "cancelled"), ("picking", "cancelled")}

    historico = _por("order_id", dados["order_status_history"])
    estados = {p["id"]: p["status"] for p in dados["orders"]}
    for pedido_id, eventos in historico.items():
        eventos = sorted(eventos, key=lambda e: e["changed_at"])
        for evento in eventos:
            assert evento["from_status"] != evento["to_status"]
            assert (evento["from_status"], evento["to_status"]) in validas
        assert eventos[-1]["to_status"] == estados[pedido_id]


def test_10_datas_respeitam_a_causalidade(dados: Dataset) -> None:
    for pagamento in dados["payments"]:
        if pagamento["captured_at"]:
            assert pagamento["authorized_at"] is not None
            assert pagamento["captured_at"] >= pagamento["authorized_at"]
    for remessa in dados["shipments"]:
        if remessa["delivered_at"] and remessa["shipped_at"]:
            assert remessa["delivered_at"] >= remessa["shipped_at"]
    for movimento in dados["inventory_movements"]:
        assert movimento["recorded_at"] >= movimento["occurred_at"]
    for chamado in dados["support_tickets"]:
        if chamado["closed_at"]:
            assert chamado["closed_at"] >= chamado["opened_at"]


def test_11_vigencias_do_mesmo_par_nao_se_sobrepoem(dados: Dataset) -> None:
    por_par: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for preco in dados["product_prices"]:
        por_par[(preco["price_list_id"], preco["product_variant_id"])].append(preco)
    for vigencias in por_par.values():
        vigencias.sort(key=lambda p: p["valid_from"])
        for anterior, seguinte in zip(vigencias, vigencias[1:]):
            assert anterior["valid_to"] is not None
            assert anterior["valid_to"] <= seguinte["valid_from"]


def test_12_cupom_usado_dentro_da_vigencia_e_das_regras(dados: Dataset) -> None:
    cupons = {c["id"]: c for c in dados["coupons"]}
    pedidos = {p["id"]: p for p in dados["orders"]}
    usos: dict[int, int] = defaultdict(int)
    for resgate in dados["coupon_redemptions"]:
        cupom = cupons[resgate["coupon_id"]]
        pedido = pedidos[resgate["order_id"]]
        assert cupom["valid_from"] <= resgate["redeemed_at"] <= cupom["valid_to"]
        assert pedido["subtotal_amount"] >= (cupom["min_order_amount"] or 0)
        assert resgate["discount_amount"] <= pedido["discount_amount"]
        usos[cupom["id"]] += 1
    for cupom_id, quantidade in usos.items():
        limite = cupons[cupom_id]["max_redemptions"]
        assert limite is None or quantidade <= limite


@pytest.mark.parametrize("dataset_fixture", ["dados", "dados_reduzidos"])
def test_13_every_shipment_contains_items(request, dataset_fixture) -> None:
    data = request.getfixturevalue(dataset_fixture)
    assert {row["id"] for row in data["shipments"]} == {
        row["shipment_id"] for row in data["shipment_items"]
    }


@pytest.mark.parametrize("dataset_fixture", ["dados", "dados_reduzidos"])
def test_14_no_product_is_sold_before_its_launch(request, dataset_fixture) -> None:
    """Null launch means unknown; a known one is at or before every sale of the product (D65)."""
    data = request.getfixturevalue(dataset_fixture)
    product_of = {row["id"]: row["product_id"] for row in data["product_variants"]}
    launched = {row["id"]: row["launched_at"] for row in data["products"]}
    placed = {row["id"]: row["placed_at"] for row in data["orders"]}
    before = [
        item["id"] for item in data["order_items"]
        if launched[product_of[item["product_variant_id"]]] is not None
        and launched[product_of[item["product_variant_id"]]] > placed[item["order_id"]]
    ]
    assert before == []
    # Not vacuous: launches are known, and some sit right at the first sale's window.
    assert sum(value is not None for value in launched.values()) > 0.8 * len(launched)


def test_livro_de_estoque_e_integro(dados: Dataset) -> None:
    """O saldo é a soma dos deltas, a versão não tem lacuna e a transferência fecha."""
    saldo: dict[tuple[int, int], int] = defaultdict(int)
    versoes: dict[tuple[int, int], list[int]] = defaultdict(list)
    correlacoes: dict[object, int] = defaultdict(int)
    chaves: set[str] = set()

    for movimento in sorted(dados["inventory_movements"], key=lambda m: m["occurred_at"]):
        chave = (movimento["warehouse_id"], movimento["product_variant_id"])
        saldo[chave] += movimento["quantity_delta"]
        assert saldo[chave] >= 0, f"saldo negativo em {chave}"
        versoes[chave].append(movimento["aggregate_version"])
        if movimento["correlation_id"]:
            correlacoes[movimento["correlation_id"]] += movimento["quantity_delta"]
        assert movimento["idempotency_key"] not in chaves
        chaves.add(movimento["idempotency_key"])

    for chave, lista in versoes.items():
        assert sorted(lista) == list(range(1, len(lista) + 1)), chave
    for total in correlacoes.values():
        assert total == 0, "transferência que não fecha dos dois lados"

    projetado = {
        (s["warehouse_id"], s["product_variant_id"]): s["quantity_on_hand"]
        for s in dados["inventory_balances"]
    }
    assert projetado == dict(saldo)


# ── Invariantes 15 a 20: o cadastro, a remessa, o chamado, a reserva, o código e o lastro ──
# Bloco 5R do plano da base dos consumidores (F24 a F27, F22 e V4). Cada uma é uma
# função que devolve as violações, para que a contraprova a exercite sobre o
# conjunto adulterado; e cada teste confere que a regra não passa por vacuidade,
# nos perfis do varejo e do legado.

PROFILES = ["dados", "dados_reduzidos", "legacy_profile"]


@pytest.fixture(scope="session")
def legacy_profile(config) -> Dataset:
    """O conjunto íntegro de que o legado parte: a semente e o fator do catálogo de falhas."""
    from mvp_ed1.generator import pipeline
    from mvp_ed1.generator.engine import Motor
    from mvp_ed1.legacy.catalogo import carregar

    catalog = carregar()
    return pipeline.gerar(Motor(config, seed=catalog.semente, fator=catalog.fator))


def _cutoffs(config):
    import datetime as dt

    from mvp_ed1.generator.engine import Motor

    end = Motor(config).fim
    process = config.tabelas["orders"].processo
    return (
        end - dt.timedelta(days=process["cliente_inativo_sem_compra_dias"]),
        end - dt.timedelta(days=process["variante_fora_de_venda_sem_venda_dias"]),
    )


def violations_15_registry_respected_in_time(data, config) -> list[str]:
    customer_cutoff, variant_cutoff = _cutoffs(config)
    customer = {row["id"]: row["status"] for row in data["customers"]}
    product = {row["id"]: row["status"] for row in data["products"]}
    variant = {
        row["id"]: (product[row["product_id"]], row["is_active"]) for row in data["product_variants"]
    }
    placed = {row["id"]: row["placed_at"] for row in data["orders"]}
    found: list[str] = []

    def buyer(kind, row, moment):
        status = customer[row["customer_id"]]
        if status in ("pending", "blocked") or (status == "inactive" and moment >= customer_cutoff):
            found.append(f"{kind} {row['id']}: cliente {status} em {moment}")

    def sold(kind, row, moment):
        status, active = variant[row["product_variant_id"]]
        if status == "draft" or ((status == "discontinued" or not active) and moment >= variant_cutoff):
            found.append(f"{kind} {row['id']}: produto {status}, variante ativa={active}, em {moment}")

    for order in data["orders"]:
        buyer("pedido", order, order["placed_at"])
    for cart in data["carts"]:
        if cart["customer_id"] is not None:
            buyer("carrinho", cart, cart["converted_at"] or cart["created_at"])
    for item in data["order_items"]:
        sold("item de pedido", item, placed[item["order_id"]])
    for item in data["cart_items"]:
        sold("item de carrinho", item, item["added_at"])
    return found


def violations_16_only_in_transit_shipment_is_lost(data) -> list[str]:
    order = {row["id"]: row["status"] for row in data["orders"]}
    return [
        f"remessa {row['id']}: lost em pedido {order[row['order_id']]}"
        for row in data["shipments"]
        if row["status"] == "lost" and order[row["order_id"]] != "shipped"
    ]


def violations_17_ticket_book_matches_status(data) -> list[str]:
    events = _por("ticket_id", data["ticket_events"])
    found: list[str] = []
    for ticket in data["support_tickets"]:
        book = events[ticket["id"]]
        resolved = [e["occurred_at"] for e in book if e["event_type"] == "resolved"]
        reopened = [e["occurred_at"] for e in book if e["event_type"] == "reopened"]
        if ticket["status"] in ("resolved", "closed") and not resolved:
            found.append(f"chamado {ticket['id']}: {ticket['status']} sem evento resolved")
        if any(not any(r < moment for r in resolved) for moment in reopened):
            found.append(f"chamado {ticket['id']}: reopened sem resolved antes")
        if reopened and ticket["status"] != "in_progress":
            found.append(f"chamado {ticket['id']}: reaberto e {ticket['status']}")
        if (ticket["closed_at"] is not None) != (ticket["status"] == "closed"):
            found.append(f"chamado {ticket['id']}: {ticket['status']} com closed_at {ticket['closed_at']}")
        if ticket["closed_at"] is not None and any(r > ticket["closed_at"] for r in resolved):
            found.append(f"chamado {ticket['id']}: resolvido depois de fechado")
    return found


def violations_18_reservation_belongs_to_an_item(data) -> list[str]:
    of_cart = {(i["cart_id"], i["product_variant_id"]): i["quantity"] for i in data["cart_items"]}
    of_order = {(i["order_id"], i["product_variant_id"]): i["quantity"] for i in data["order_items"]}
    moved = {(m["warehouse_id"], m["product_variant_id"]) for m in data["inventory_movements"]}
    seen: set[tuple] = set()
    found: list[str] = []
    for row in data["stock_reservations"]:
        if row["cart_id"] is not None:
            key, quantity = ("cart", row["cart_id"], row["product_variant_id"]), of_cart.get(
                (row["cart_id"], row["product_variant_id"])
            )
        else:
            key, quantity = ("order", row["order_id"], row["product_variant_id"]), of_order.get(
                (row["order_id"], row["product_variant_id"])
            )
        if quantity is None:
            found.append(f"reserva {row['id']}: SKU fora da origem {key}")
        elif quantity != row["quantity"]:
            found.append(f"reserva {row['id']}: quantidade {row['quantity']}, item {quantity}")
        if key in seen:
            found.append(f"reserva {row['id']}: item {key} reservado duas vezes")
        seen.add(key)
        if (row["warehouse_id"], row["product_variant_id"]) not in moved:
            found.append(f"reserva {row['id']}: armazém sem movimento do SKU")
    return found


def violations_19_gateway_code_follows_result(data, config) -> list[str]:
    codes = config.tabelas["payment_transactions"].processo["codigo_de_retorno"]
    allowed = {
        "succeeded": {str(codes["succeeded"])},
        "pending": {str(codes["pending"])},
        "failed": {str(code) for code in codes["failed"]},
    }
    return [
        f"transação {row['id']}: {row['result']} com código {row['gateway_response_code']}"
        for row in data["payment_transactions"]
        if row["gateway_response_code"] not in allowed[row["result"]]
    ]


def violations_20_stock_is_backed_from_the_opening(data, config) -> list[str]:
    from mvp_ed1.generator.engine import Motor

    start = Motor(config).inicio
    openings: dict[tuple[int, int], int] = defaultdict(int)
    found: list[str] = []
    for row in data["inventory_movements"]:
        pair = (row["warehouse_id"], row["product_variant_id"])
        if row["source_id"] == "ESTOQUE-INICIAL":
            openings[pair] += 1
            if row["occurred_at"] != start or row["aggregate_version"] != 1:
                found.append(f"par {pair}: abertura fora do começo do período")
        if row["source_id"] == "AJU-CONFERENCIA" or (row["metadata"] or {}).get("corrige"):
            found.append(f"par {pair}: ajuste criado para cobrir a saída {row['source_id']}")
    found += [f"par {pair}: {count} aberturas" for pair, count in openings.items() if count > 1]
    balance: dict[tuple[int, int], int] = defaultdict(int)
    for row in sorted(data["inventory_movements"], key=lambda m: m["aggregate_version"]):
        pair = (row["warehouse_id"], row["product_variant_id"])
        balance[pair] += row["quantity_delta"]
        if balance[pair] < 0:
            found.append(f"par {pair}: saldo negativo na versão {row['aggregate_version']}")
    return found


@pytest.mark.parametrize("profile", PROFILES)
def test_15_registry_status_is_respected_in_time(request, config, profile) -> None:
    """Quem não pode comprar não compra, e o que não está à venda não vende (F24)."""
    data = request.getfixturevalue(profile)
    assert violations_15_registry_respected_in_time(data, config) == []
    # Sem vacuidade: os estados continuam no cadastro, e a venda antiga do
    # `inactive` e do `discontinued` continua no dado.
    customer = {row["id"]: row["status"] for row in data["customers"]}
    product = {row["id"]: row["status"] for row in data["products"]}
    variant = {row["id"]: product[row["product_id"]] for row in data["product_variants"]}
    assert set(customer.values()) == {"active", "inactive", "blocked", "pending"}
    assert set(product.values()) == {"active", "discontinued", "draft"}
    assert any(customer[row["customer_id"]] == "inactive" for row in data["orders"])
    assert any(variant[row["product_variant_id"]] == "discontinued" for row in data["order_items"])
    assert any(variant[row["product_variant_id"]] == "discontinued" for row in data["cart_items"])


@pytest.mark.parametrize("profile", PROFILES)
def test_16_only_a_shipment_in_transit_is_lost(request, profile) -> None:
    """Remessa extraviada é de pedido `shipped`, nunca de pedido entregue (F25)."""
    data = request.getfixturevalue(profile)
    assert violations_16_only_in_transit_shipment_is_lost(data) == []
    assert any(row["status"] == "lost" for row in data["shipments"])


@pytest.mark.parametrize("profile", PROFILES)
def test_17_ticket_book_matches_its_status(request, profile) -> None:
    """Resolução no livro, reabertura depois dela e `closed_at` só no `closed` (F26)."""
    data = request.getfixturevalue(profile)
    assert violations_17_ticket_book_matches_status(data) == []
    statuses = {row["status"] for row in data["support_tickets"]}
    assert {"resolved", "closed", "in_progress"} <= statuses
    assert any(row["event_type"] == "reopened" for row in data["ticket_events"])


@pytest.mark.parametrize("profile", PROFILES)
def test_18_reservation_belongs_to_an_item_of_its_origin(request, profile) -> None:
    """A reserva é do SKU e da quantidade de um item do carrinho ou do pedido dela (F27)."""
    data = request.getfixturevalue(profile)
    assert violations_18_reservation_belongs_to_an_item(data) == []
    assert any(row["cart_id"] is not None for row in data["stock_reservations"])
    assert any(row["order_id"] is not None for row in data["stock_reservations"])


@pytest.mark.parametrize("profile", PROFILES)
def test_19_gateway_code_follows_the_result(request, config, profile) -> None:
    """O código do adquirente segue o resultado da transação (F22)."""
    data = request.getfixturevalue(profile)
    assert violations_19_gateway_code_follows_result(data, config) == []
    # Os três resultados em todo perfil: a autorização pendente e a aprovada
    # sem captura têm a cobertura garantida pelo gerador (F29).
    results = {row["result"] for row in data["payment_transactions"]}
    assert results == {"succeeded", "failed", "pending"}
    assert {"pending", "authorized"} <= {row["status"] for row in data["payments"]}
    refusals = config.tabelas["payment_transactions"].processo["codigo_de_retorno"]["failed"]
    failed = [r["gateway_response_code"] for r in data["payment_transactions"] if r["result"] == "failed"]
    if len(failed) >= len(refusals):
        assert set(failed) == {str(code) for code in refusals}


@pytest.mark.parametrize("profile", PROFILES)
def test_20_stock_is_backed_from_the_opening(request, config, profile) -> None:
    """Nenhum ajuste criado para cobrir uma saída: o lastro que faltaria vem da abertura (V4)."""
    data = request.getfixturevalue(profile)
    assert violations_20_stock_is_backed_from_the_opening(data, config) == []
    # Sem vacuidade: há par que só tem estoque porque a abertura foi dimensionada
    # pela demanda — sem ela, a primeira saída dele não teria lastro.
    by_pair = defaultdict(list)
    for row in data["inventory_movements"]:
        by_pair[(row["warehouse_id"], row["product_variant_id"])].append(row)
    assert any(
        rows[0]["source_id"] == "ESTOQUE-INICIAL" and rows[1]["quantity_delta"] < 0
        for rows in (sorted(v, key=lambda m: m["aggregate_version"]) for v in by_pair.values())
        if len(rows) > 1
    )


def _tampered(data, table: str, row_id, key: str = "id", **changes):
    """O conjunto com uma linha trocada — os demais objetos são os mesmos, intocados."""
    tables = {name: data[name] for name in data}
    tables[table] = [dict(row, **changes) if row[key] == row_id else row for row in data[table]]
    return tables


def test_counterproofs_of_15_to_20(dados_reduzidos: Dataset, config) -> None:
    """Cada defeito que o gerador tinha, recolocado no dado, é acusado pela invariante dele."""
    import datetime as dt

    data = dados_reduzidos
    status_of = {row["id"]: row["status"] for row in data["products"]}
    order = data["orders"][0]
    late = _cutoffs(config)[0] + dt.timedelta(days=1)

    # 15: o cliente bloqueado que compra; o inativo que compra na janela; o `draft` que vende.
    blocked = next(row["id"] for row in data["customers"] if row["status"] == "blocked")
    inactive = next(row["id"] for row in data["customers"] if row["status"] == "inactive")
    draft = next(row["id"] for row in data["product_variants"] if status_of[row["product_id"]] == "draft")
    for tampered in (
        _tampered(data, "orders", order["id"], customer_id=blocked),
        _tampered(data, "orders", order["id"], customer_id=inactive, placed_at=late),
        _tampered(data, "order_items", data["order_items"][0]["id"], product_variant_id=draft),
        _tampered(data, "cart_items", data["cart_items"][0]["id"], product_variant_id=draft),
    ):
        assert violations_15_registry_respected_in_time(tampered, config)

    # 16: a remessa entregue que vira extraviada.
    delivered = next(row["id"] for row in data["shipments"] if row["status"] == "delivered")
    assert violations_16_only_in_transit_shipment_is_lost(
        _tampered(data, "shipments", delivered, status="lost")
    )

    # 17: a resolução que some; a reabertura sem ela; o `resolved` com data de fechamento.
    resolved = next(row for row in data["support_tickets"] if row["status"] == "resolved")
    reopening = next(row for row in data["ticket_events"] if row["event_type"] == "reopened")
    first_resolution = next(
        row for row in data["ticket_events"]
        if row["ticket_id"] == reopening["ticket_id"] and row["event_type"] == "resolved"
    )
    lost_resolution = next(
        row for row in data["ticket_events"]
        if row["ticket_id"] == resolved["id"] and row["event_type"] == "resolved"
    )
    for tampered in (
        _tampered(data, "ticket_events", lost_resolution["id"], event_type="message"),
        _tampered(data, "ticket_events", first_resolution["id"], event_type="message"),
        _tampered(data, "support_tickets", resolved["id"], closed_at=resolved["opened_at"]),
    ):
        assert violations_17_ticket_book_matches_status(tampered)

    # 18: a reserva de um SKU que não é da origem; a quantidade que não é a do item.
    reservation = data["stock_reservations"][0]
    in_origin = {
        row["product_variant_id"] for row in data["cart_items"] if row["cart_id"] == reservation["cart_id"]
    } | {
        row["product_variant_id"] for row in data["order_items"] if row["order_id"] == reservation["order_id"]
    }
    stranger = next(row["id"] for row in data["product_variants"] if row["id"] not in in_origin)
    for tampered in (
        _tampered(data, "stock_reservations", reservation["id"], product_variant_id=stranger),
        _tampered(data, "stock_reservations", reservation["id"], quantity=reservation["quantity"] + 1),
    ):
        assert violations_18_reservation_belongs_to_an_item(tampered)

    # 20: a correção-relâmpago de volta; e a abertura que não cobre a demanda do par.
    opening = next(row for row in data["inventory_movements"] if row["source_id"] == "ESTOQUE-INICIAL")
    entry = next(
        row for row in data["inventory_movements"]
        if row["movement_type"] == "adjustment_in" and row["source_id"] != "ESTOQUE-INICIAL"
    )
    for tampered in (
        _tampered(data, "inventory_movements", entry["movement_id"], "movement_id", source_id="AJU-CONFERENCIA"),
        _tampered(data, "inventory_movements", opening["movement_id"], "movement_id", quantity_delta=-10_000),
    ):
        assert violations_20_stock_is_backed_from_the_opening(tampered, config)

    # 19: o `51` numa transação aprovada, que foi o achado.
    approved = next(row["id"] for row in data["payment_transactions"] if row["result"] == "succeeded")
    assert violations_19_gateway_code_follows_result(
        _tampered(data, "payment_transactions", approved, gateway_response_code="51"), config
    )
