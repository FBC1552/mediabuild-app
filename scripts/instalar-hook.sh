#!/bin/sh
# Instala o hook que roda a trava de publicação antes de todo `git push`.
# Termos específicos (empresa, clientes) ficam num arquivo FORA do repo:
#   export PUBLICACAO_BLOQUEIO=/caminho/para/.bloqueio-local.txt
set -e
raiz="$(git rev-parse --show-toplevel)"
cat > "$raiz/.git/hooks/pre-push" <<'HOOK'
#!/bin/sh
raiz="$(git rev-parse --show-toplevel)"
python "$raiz/scripts/verificar_publicacao.py" "$raiz" || { echo "push bloqueado pela trava de publicação"; exit 1; }
HOOK
chmod +x "$raiz/.git/hooks/pre-push"
echo "hook pre-push instalado"
