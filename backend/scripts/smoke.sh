#!/usr/bin/env bash
# Vérification d'intégration SANS toucher à la base ni aux serveurs de
# l'utilisateur. Règle d'or (AGENTS.md) : NE JAMAIS supprimer
# backend/skilljob.db ni faire de taskkill global.
#
# Usage : bash scripts/smoke.sh
# - base isolée : backend/.smoke/smoke.db (créée puis supprimée)
# - port isolé  : 8123
# - arrêt ciblé : uniquement le PID démarré ici

set -e
cd "$(dirname "$0")/.."

SMOKE_DIR=".smoke"
SMOKE_DB="$SMOKE_DIR/smoke.db"
SMOKE_PORT="${SMOKE_PORT:-8123}"
mkdir -p "$SMOKE_DIR"
rm -f "$SMOKE_DB"

# Base isolée + venv
export DATABASE_URL="sqlite:///./$SMOKE_DB"
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate; fi

echo "=== Vérification isolée (base: $SMOKE_DB, port: $SMOKE_PORT) ==="
python -m uvicorn app.main:app --port "$SMOKE_PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true; rm -rf "$SMOKE_DIR"' EXIT

# Attente du démarrage
for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://localhost:$SMOKE_PORT/api/health"; then break; fi
  sleep 1
done

BASE="http://localhost:$SMOKE_PORT"

# Compte de service pour les tests
TOKEN=$(curl -s -X POST "$BASE/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"demo@orientskill.cm","password":"demo1234"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

for ep in "/api/market/trends" "/api/jobs?limit=3" "/api/careers" "/api/learning" \
          "/api/geo" "/api/institutional" "/api/entrepreneurship" "/api/dashboard" \
          "/api/profile" "/api/documents" "/api/cv-templates" "/api/questionnaire"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE$ep")
  status=$([ "$code" = "200" ] && echo "OK " || echo "!! ")
  echo "  $status $code $ep"
  [ "$code" = "200" ] || FAILED=1
done

echo ""
if [ -n "$FAILED" ]; then
  echo "=== ÉCHEC : au moins un endpoint a échoué ==="
  exit 1
fi
echo "=== Vérification réussie (base et serveurs utilisateur intacts) ==="
