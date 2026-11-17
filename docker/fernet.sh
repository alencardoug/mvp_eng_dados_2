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
# `garantir` só troca a chave **inválida**. Com ela o Airflow nunca conseguiu
# cifrar nada, então não há dado cifrado a perder. Chave válida fica como está,
# porque trocá-la tornaria ilegível o que já foi cifrado com ela. Chave ausente
# não é assunto deste script: quem a acrescenta é o `make env` e o `airflow-up`.
set -euo pipefail

gerar() {
	# `head -c 32` são 32 bytes, e `base64` os escreve em 44 caracteres; o `tr`
	# troca `+` e `/` pelos dois do alfabeto seguro para URL (RFC 4648 §5).
	head -c 32 /dev/urandom | base64 | tr '+/' '-_'
}

valida() {
	local chave="$1"
	[[ "$chave" =~ ^[A-Za-z0-9_-]{43}=$ ]] || return 1
	local bytes
	bytes=$(printf '%s' "$chave" | tr '_-' '/+' | base64 -d 2>/dev/null | wc -c) || return 1
	[ "$bytes" -eq 32 ]
}

garantir() {
	local env="$1"
	[ -f "$env" ] || { echo "fernet: $env não existe" >&2; return 1; }
	local atual
	atual=$(sed -n 's/^AIRFLOW_FERNET_KEY=//p' "$env" | tail -1)
	[ -n "$atual" ] || return 0
	valida "$atual" && return 0
	local nova
	nova=$(gerar)
	# A chave nova só tem `[A-Za-z0-9_=-]`: nenhum caractere especial para o `sed`.
	sed -i "s|^AIRFLOW_FERNET_KEY=.*|AIRFLOW_FERNET_KEY=$nova|" "$env"
	valida "$(sed -n 's/^AIRFLOW_FERNET_KEY=//p' "$env" | tail -1)" || {
		echo "fernet: a troca da chave em $env não conferiu" >&2; return 1; }
	echo "AIRFLOW_FERNET_KEY inválida em $env (D64): trocada por uma chave Fernet válida. Nada cifrado se perde:"
	echo "  com a chave antiga o Airflow não cifrava nada. Os contêineres do Airflow são recriados com a nova."
}

case "${1:-}" in
	gerar) gerar ;;
	valida) valida "${2:?uso: fernet.sh valida <chave>}" ;;
	garantir) garantir "${2:?uso: fernet.sh garantir <arquivo .env>}" ;;
	*) echo "uso: docker/fernet.sh gerar | valida <chave> | garantir <arquivo .env>" >&2; exit 2 ;;
esac
