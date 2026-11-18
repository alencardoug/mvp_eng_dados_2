"""Domínio de fornecedores e compras — 5 tabelas.

É aqui que o estoque nasce. A invariante 6 — recebimento não supera o
solicitado — atravessa `goods_receipt_items` e `purchase_order_items`, e por
isso o modelo não a expressa como `CHECK`: ela é garantida na geração e
cobrada por teste.

O estado da ordem **não** é sorteado: é recalculado do que foi efetivamente
recebido. Ordem marcada `received` sem recebimento é o tipo de incoerência que
passa em toda constraint e só aparece na reconciliação.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from mvp_ed1.generator.dataset import Dataset
from mvp_ed1.generator.engine import Motor
from mvp_ed1.generator.rng import cobrir, dinheiro, preco, repartir

_SEM_RECEBIMENTO = ("draft", "placed", "cancelled")


def fornecedores(motor: Motor, dados: Dataset) -> None:
    n = motor.linhas("suppliers")
    dados.guardar("suppliers", motor.preencher("suppliers", [{} for _ in range(n)]))


def ordens(motor: Motor, dados: Dataset) -> None:
    """Ordens, itens e recebimentos — sem as quantidades, que vêm da venda (V5).

    A estrutura sai aqui, com os mesmos sorteios de sempre: quantas ordens, que itens, que
    recebimentos, em que armazém e quando, que fração no recebimento parcial. A quantidade de
    cada item e o estado da ordem saem em `dimensionar_pela_demanda`, depois das remessas.
    """
    ordens_linhas = _ordens(motor, dados)
    itens = _itens(motor, dados, ordens_linhas)
    _recebimentos(motor, dados, ordens_linhas, itens)


def dimensionar_pela_demanda(motor: Motor, dados: Dataset) -> None:
    """A quantidade de cada item de compra pela venda que ele cobre (V5; Q73 do plano da reabertura).

    Para cada item, a venda do par — o armazém de cada recebimento × o SKU — nos
    `cobertura_da_compra_dias` seguintes a ele; o item sem recebimento cobre a venda do SKU em todos
    os armazéns depois da ordem. O pedido nunca é menor que um por lote, nem que dois por lote na
    ordem parcialmente recebida. O recebido sai do pedido: inteiro no recebimento comum, repartido
    entre os lotes sem perder resto, e a fração sorteada no parcial, sempre abaixo do pedido
    (invariante 6). Com as quantidades, o custo do item, o total da ordem e o estado dela.
    """
    from mvp_ed1.generator.domains.estoque import demanda_por_par

    cobertura = dt.timedelta(days=motor.config.tabelas["purchase_order_items"].processo["cobertura_da_compra_dias"])
    demanda = demanda_por_par(dados)
    por_sku: dict[int, list[tuple[dt.datetime, int]]] = {}
    for (_, sku), saidas in demanda.items():
        por_sku.setdefault(sku, []).extend(saidas)

    def adiante(saidas, desde):
        return sum(q for quando, q in saidas if desde < quando <= desde + cobertura)

    ordens_linhas = dados["purchase_orders"]
    ordem_de = {o["id"]: o for o in ordens_linhas}
    recebidos_do_item: dict[int, list[dict]] = {}
    for recebido in dados["goods_receipt_items"]:
        recebidos_do_item.setdefault(recebido["purchase_order_item_id"], []).append(recebido)

    for item in dados["purchase_order_items"]:
        ordem = ordem_de[item["purchase_order_id"]]
        recebidos = recebidos_do_item.get(item["id"], [])
        if recebidos:
            venda = sum(adiante(demanda.get((r["__warehouse_id"], item["product_variant_id"]), ()), r["created_at"])
                        for r in recebidos)
            lotes = recebidos[0]["__lotes"]
            parcial = ordem["__destino"] == "partially_received"
            minimo = lotes * (2 if parcial else 1)
        else:
            venda = adiante(por_sku.get(item["product_variant_id"], ()), ordem["ordered_at"])
            lotes, parcial, minimo = 1, False, 1
        pedida = max(minimo, venda)
        item["quantity_ordered"] = pedida
        item["total_cost"] = dinheiro(item["unit_cost"] * pedida)
        if recebidos:
            _repartir(pedida, sorted(recebidos, key=lambda r: r["__lote"]), parcial)

    total_por_ordem: dict[int, Decimal] = {}
    for item in dados["purchase_order_items"]:
        total_por_ordem[item["purchase_order_id"]] = (
            total_por_ordem.get(item["purchase_order_id"], Decimal("0")) + item["total_cost"])
    for ordem in ordens_linhas:
        ordem["total_amount"] = dinheiro(total_por_ordem.get(ordem["id"], Decimal("0")))
    _fechar_estado(ordens_linhas, dados["purchase_order_items"], dados["goods_receipts"], dados["goods_receipt_items"])


def _repartir(pedida: int, recebidos: list[dict], parcial: bool) -> None:
    """O recebido de cada lote do item: o pedido inteiro (ou a fração dele, no parcial), sem perder resto."""
    lotes = len(recebidos)
    if parcial:
        # A fração é a sorteada no primeiro lote; o parcial fica estritamente abaixo do pedido.
        alvo = min(pedida - 1, max(lotes, int(Decimal(pedida) * recebidos[0]["__fracao"])))
    else:
        alvo = pedida
    base = alvo // lotes
    for indice, recebido in enumerate(recebidos):
        recebido["quantity_received"] = base + (alvo - base * lotes if indice == lotes - 1 else 0)


def _ordens(motor: Motor, dados: Dataset) -> list[dict]:
    fornecedores_ids = [linha["id"] for linha in dados["suppliers"] if not linha["deleted_at"]]
    fonte = motor.fonte("purchase_orders")
    processo = motor.config.tabelas["purchase_orders"].processo
    minimo, maximo = processo["prazo_prometido_dias"]

    total = motor.linhas("purchase_orders")
    destinos = cobrir(
        [fonte.ponderada(processo["destino"]) for _ in range(total)],
        tuple(processo["destino"]),
    )

    esqueletos: list[dict] = []
    for indice in range(total):
        emitida = motor.relogio.sazonal(fonte)
        esqueletos.append(
            {
                "supplier_id": fonte.escolha(fornecedores_ids),
                "ordered_at": emitida,
                # Prazo prometido pode cair depois de `as_of_date`: é promessa,
                # não evento — e ordem recente com entrega futura é o normal.
                "expected_at": emitida + _dias(fonte, minimo, maximo),
                "status": "draft",
                "total_amount": Decimal("0"),
                # Documento comercial emitido não é apagado logicamente: ele é
                # cancelado por estado. Exclusão lógica em linha de documento
                # deixaria o total do cabeçalho sem os itens que o formaram.
                "deleted_at": None,
                "__destino": destinos[indice],
            }
        )
    return dados.guardar("purchase_orders", motor.preencher("purchase_orders", esqueletos))


def _itens(motor: Motor, dados: Dataset, ordens_linhas: list[dict]) -> list[dict]:
    variantes = dados["product_variants"]
    fonte = motor.fonte("purchase_order_items")
    processo = motor.config.tabelas["purchase_order_items"].processo
    minimo_itens, maximo_itens = processo["itens_por_ordem"]

    por_ordem = repartir(
        motor.linhas("purchase_order_items"), len(ordens_linhas), fonte,
        minimo=minimo_itens, maximo=maximo_itens,
    )

    esqueletos: list[dict] = []
    for ordem, quantidade in zip(ordens_linhas, por_ordem):
        # Variantes distintas: `uq_purchase_order_items_ordem_variante` recusa
        # o mesmo SKU duas vezes na mesma ordem.
        for variante in fonte.amostra(variantes, quantidade):
            # A quantidade vem da venda que o item cobre, e a venda ainda não existe aqui:
            # `dimensionar_pela_demanda` a escreve depois das remessas (V5).
            pedida = 0
            custo = preco(variante["__custo"] * Decimal(str(fonte.rng.uniform(0.9, 1.08))))
            esqueletos.append(
                {
                    "purchase_order_id": ordem["id"],
                    "product_variant_id": variante["id"],
                    "quantity_ordered": pedida,
                    "unit_cost": custo,
                    "total_cost": dinheiro(custo * pedida),
                    "deleted_at": None,
                    "__momento": ordem["ordered_at"],
                }
            )
    itens = dados.guardar("purchase_order_items", motor.preencher("purchase_order_items", esqueletos))

    # O total da ordem é a soma dos itens — o mesmo padrão de denormalização por
    # imutabilidade do fato que `orders` usa (Modelo de Dados §2.10). Sai em
    # `dimensionar_pela_demanda`, com as quantidades.
    return itens


def _recebimentos(
    motor: Motor, dados: Dataset, ordens_linhas: list[dict], itens: list[dict]
) -> tuple[list[dict], list[dict]]:
    armazens = dados["warehouses"]
    fonte = motor.fonte("goods_receipts")
    processo = motor.config.tabelas["goods_receipts"].processo
    minimo_dias, maximo_dias = processo["prazo_de_recebimento_dias"]
    fracao_min, fracao_max = motor.config.tabelas["goods_receipt_items"].processo["fracao_parcial"]

    itens_por_ordem: dict[int, list[dict]] = {}
    for item in itens:
        itens_por_ordem.setdefault(item["purchase_order_id"], []).append(item)

    recebiveis = [o for o in ordens_linhas if o["__destino"] not in _SEM_RECEBIMENTO]
    alvo = motor.linhas("goods_receipts")
    # Entregas em duas remessas: é o que leva a contagem de recebimentos acima
    # da de ordens sem inventar ordem nenhuma.
    com_dois = set(fonte.amostra(range(len(recebiveis)), max(alvo - len(recebiveis), 0)))

    recebimentos: list[dict] = []
    itens_recebidos: list[dict] = []
    for indice, ordem in enumerate(recebiveis):
        do_pedido = itens_por_ordem.get(ordem["id"], [])
        if not do_pedido:
            continue
        armazem = fonte.escolha(armazens)
        lotes = 2 if indice in com_dois else 1
        parcial = ordem["__destino"] == "partially_received"

        for lote in range(lotes):
            recebido_em = motor.relogio.depois(
                ordem["ordered_at"], fonte, minimo_dias * 24, maximo_dias * 24
            )
            # Cobertura antes do sorteio: os três primeiros recebimentos levam
            # um estado cada, para que `rejected` exista em qualquer semente.
            estados_possiveis = tuple(processo["estado"])
            estado = (
                estados_possiveis[len(recebimentos)]
                if len(recebimentos) < len(estados_possiveis)
                else fonte.ponderada(processo["estado"])
            )
            recebimento = {
                "id": len(recebimentos) + 1,
                "purchase_order_id": ordem["id"],
                "warehouse_id": armazem["id"],
                "received_at": recebido_em,
                "status": estado,
                "deleted_at": None,
            }
            recebimentos.append(recebimento)

            for item in do_pedido:
                # A fração do parcial é sorteada aqui, como sempre, e guardada; a quantidade sai
                # do pedido em `dimensionar_pela_demanda`, depois das remessas (V5).
                fracao = Decimal(str(fonte.rng.uniform(fracao_min, fracao_max))) if parcial else None
                itens_recebidos.append(
                    {
                        "goods_receipt_id": recebimento["id"],
                        "purchase_order_item_id": item["id"],
                        "quantity_received": 0,
                        "__lote": lote,
                        "__lotes": lotes,
                        "__fracao": fracao,
                        "unit_cost": item["unit_cost"],
                        "deleted_at": None,
                        "__momento": recebido_em,
                        "__warehouse_id": armazem["id"],
                        "__product_variant_id": item["product_variant_id"],
                        "__status": estado,
                    }
                )

    dados.guardar("goods_receipts", motor.preencher("goods_receipts", recebimentos))
    dados.guardar("goods_receipt_items", motor.preencher("goods_receipt_items", itens_recebidos))
    return recebimentos, itens_recebidos


def _fechar_estado(
    ordens_linhas: list[dict],
    itens: list[dict],
    recebimentos: list[dict],
    itens_recebidos: list[dict],
) -> None:
    """Estado da ordem a partir do que foi recebido, e nunca o contrário.

    Só recebimento `completed` conta. Um recebimento `rejected` deixa a ordem
    onde ela estava — que é o comportamento que a operação real tem, e o que a
    reconciliação da Etapa 6 vai cobrar.
    """
    ordem_do_recebimento = {r["id"]: r["purchase_order_id"] for r in recebimentos}
    concluido = {r["id"] for r in recebimentos if r["status"] == "completed"}

    pedido_por_ordem: dict[int, int] = {}
    for item in itens:
        pedido_por_ordem[item["purchase_order_id"]] = (
            pedido_por_ordem.get(item["purchase_order_id"], 0) + item["quantity_ordered"]
        )
    recebido_por_ordem: dict[int, int] = {}
    for item in itens_recebidos:
        if item["goods_receipt_id"] not in concluido:
            continue
        ordem = ordem_do_recebimento[item["goods_receipt_id"]]
        recebido_por_ordem[ordem] = recebido_por_ordem.get(ordem, 0) + item["quantity_received"]

    for ordem in ordens_linhas:
        pedido = pedido_por_ordem.get(ordem["id"], 0)
        recebido = recebido_por_ordem.get(ordem["id"], 0)
        destino = ordem["__destino"]
        if destino == "cancelled":
            ordem["status"] = "cancelled"
        elif recebido <= 0:
            ordem["status"] = "draft" if destino == "draft" else "placed"
        elif recebido >= pedido:
            ordem["status"] = "received"
        else:
            ordem["status"] = "partially_received"


def _dias(fonte, minimo: int, maximo: int) -> dt.timedelta:
    return dt.timedelta(days=fonte.inteiro(minimo, maximo))
