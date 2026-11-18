#!/usr/bin/env bash
# A chave Fernet do Airflow: gerar uma válida e trocar a inválida (D64).
#
# O Airflow cifra Connections e Variables com `AIRFLOW__CORE__FERNET_KEY`, e a
# chave tem de ser 32 bytes em base64 seguro para URL — 44 caracteres, o último
# `=`. Até 17/11/2026 o `Makefile` a gerava como as senhas, 32 caracteres
# alfanuméricos, e o Airflow recusava: "Fernet key must be 32 url-safe
# base64-encoded bytes" (Pendências, D64, medido em 04/10/2026).
#
# Uso:  docker/fernet.sh gerar           imprime uma chave nova
#       docker/fernet.sh valida <chave>  sai 0 se a chave é válida, 1 se não
#       docker/fernet.sh garantir <env>  troca no arquivo a chave inválida
#
# `garantir` só troca a chave que o projeto **gerava** inválida (ver `LEGADA`). Com ela o Airflow
# nunca conseguiu cifrar nada, então não há dado cifrado a perder. Qualquer outra grafia fica como
# está, porque trocar uma chave utilizável tornaria ilegível o que já foi cifrado com ela. Chave
# ausente não é assunto deste script: quem a acrescenta é o `make env` e o `airflow-up`.
set -euo pipefail

gerar() {
	# `head -c 32` são 32 bytes, e `base64` os escreve em 44 caracteres; o `tr`
	# troca `+` e `/` pelos dois do alfabeto seguro para URL (RFC 4648 §5).
	head -c 32 /dev/urandom | base64 | tr '+/' '-_'
}

# Válida é o que o `Fernet` do Airflow aceita: 32 bytes por `urlsafe_b64decode`, que também aceita o
# alfabeto padrão (`+` e `/`) — medido na revisão do Bloco 1 (RVB1-1-01). Recusá-la a faria ser trocada.
valida() {
	local chave="$1"
	[[ "$chave" =~ ^[A-Za-z0-9_+/-]{43}=$ ]] || return 1
	local bytes
	bytes=$(printf '%s' "$chave" | tr '_-' '/+' | base64 -d 2>/dev/null | wc -c) || return 1
	[ "$bytes" -eq 32 ]
}

# A única forma trocada é a que o projeto gerava errado até 17/11/2026: uma linha só que menciona a
# chave, exatamente `AIRFLOW_FERNET_KEY=` seguido de 32 caracteres alfanuméricos. Ela nunca é chave
# Fernet: 32 caracteres de base64 dão 24 bytes, e o Fernet pede 32.
#
# **Nenhuma outra grafia autoriza a sobrescrita** (RVB1-2-01, RVB1-2-02). Aspas, escapes, espaço antes
# das aspas, `export`, comentário, *padding* a mais: o Compose e o `urlsafe_b64decode` do Fernet aceitam
# formas que um *parser* daqui leria diferente, e cada leitura errada trocaria uma chave válida —
# tornando ilegível o que ela cifrou. Forma que não é a gerada fica como está, com um aviso quando não é
# a canônica: se for inválida, o Airflow recusa na subida, alto, e quem escreveu a linha decide.
LEGADA='^AIRFLOW_FERNET_KEY=[A-Za-z0-9]{32}$'

garantir() {
	local env="$1"
	[ -f "$env" ] || { echo "fernet: $env não existe" >&2; return 1; }
	local linhas
	linhas=$(grep -c 'AIRFLOW_FERNET_KEY' "$env" || true)
	[ "$linhas" -eq 0 ] && return 0
	if [ "$linhas" -eq 1 ] && grep -Eq "$LEGADA" "$env"; then
		local nova
		nova=$(gerar)
		# A chave nova só tem `[A-Za-z0-9_=-]`: nenhum caractere especial para o `sed`.
		sed -i -E "s|$LEGADA|AIRFLOW_FERNET_KEY=$nova|" "$env"
		grep -qx "AIRFLOW_FERNET_KEY=$nova" "$env" && valida "$nova" || {
			echo "fernet: a troca da chave em $env não conferiu" >&2; return 1; }
		echo "AIRFLOW_FERNET_KEY inválida em $env (D64): trocada por uma chave Fernet válida. Nada cifrado se perde:"
		echo "  com a chave antiga o Airflow não cifrava nada. Os contêineres do Airflow são recriados com a nova."
		return 0
	fi
	local cru
	cru=$(sed -n 's/^AIRFLOW_FERNET_KEY=//p' "$env" | tail -1)
	if [ "$linhas" -ne 1 ] || ! valida "$cru"; then
		echo "fernet: AIRFLOW_FERNET_KEY em $env não está na forma que este script gera nem na que ele troca;" >&2
		echo "  nada foi alterado. Se o Airflow recusar a chave, corrija a linha à mão." >&2
	fi
	return 0
}

case "${1:-}" in
	gerar) gerar ;;
	valida) valida "${2:?uso: fernet.sh valida <chave>}" ;;
	garantir) garantir "${2:?uso: fernet.sh garantir <arquivo .env>}" ;;
	*) echo "uso: docker/fernet.sh gerar | valida <chave> | garantir <arquivo .env>" >&2; exit 2 ;;
esac
