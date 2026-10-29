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

# Base isolée + venv + dépôts isolés (photos, pièces, photos d'offres) :
# jamais le dossier uploads/ réel de l'utilisateur.
export DATABASE_URL="sqlite:///./$SMOKE_DB"
export UPLOAD_DIR="$PWD/$SMOKE_DIR/uploads"
# Aucun planificateur pendant le smoke : pas d'e-mail ni de requête réseau
# imprévus, et aucune course avec les données de test.
export SOURCE_SCHEDULER_ENABLED=0
export DIGEST_SCHEDULER_ENABLED=0
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate; fi

echo "=== Vérification isolée (base: $SMOKE_DB, port: $SMOKE_PORT) ==="
python -m uvicorn app.main:app --port "$SMOKE_PORT" --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true; wait $SERVER_PID 2>/dev/null || true; rm -rf "$SMOKE_DIR"' EXIT

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
          "/api/geo" "/api/institutional" "/api/institutional/minesup" \
          "/api/entrepreneurship" "/api/dashboard" \
          "/api/profile" "/api/documents" "/api/cv-templates" "/api/questionnaire"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE$ep")
  status=$([ "$code" = "200" ] && echo "OK " || echo "!! ")
  echo "  $status $code $ep"
  [ "$code" = "200" ] || FAILED=1
done

# ---------- Partage du CV généraliste (base isolée) ----------
CV_ID=$(curl -s -X POST "$BASE/api/cv" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"template":"classique"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# ---------- Réimport d'un CV de la bibliothèque (brouillon, sans sauvegarde) ----------
IMPORT_CODE=$(curl -s -o .smoke/import.json -w "%{http_code}" \
  -X POST "$BASE/api/profile/import-cv/library" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"document_id\":$CV_ID}")
IMPORT_OK=$(python -c "import sys,json;d=json.load(open('.smoke/import.json',encoding='utf-8'));print(d['report']['skills_found'] >= 1 and bool(d['draft']['title']))")
echo "  $([ "$IMPORT_CODE" = "200" ] && [ "$IMPORT_OK" = "True" ] && echo "OK " || echo "!! ") $IMPORT_CODE import bibliothèque sans sauvegarde"
[ "$IMPORT_CODE" = "200" ] && [ "$IMPORT_OK" = "True" ] || FAILED=1

SHARE=$(curl -s -X PUT "$BASE/api/profile/cv-visibility" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"visible\":true,\"document_id\":$CV_ID}")
VISIBLE=$(printf '%s' "$SHARE" | python -c "import sys,json;print(json.load(sys.stdin)['visible'])")
echo "  $([ "$VISIBLE" = "True" ] && echo "OK " || echo "!! ") partage opt-in du CV généraliste"
[ "$VISIBLE" = "True" ] || FAILED=1
curl -s -o /dev/null -X PUT "$BASE/api/profile/cv-visibility" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"visible":false}'

# ---------- Vérification v18 : PDF de programme + photo d'offre (isolés) ----------
ADMIN_TOKEN=$(curl -s -X POST "$BASE/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@orientskill.cm","password":"admin1234"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

python -c 'import pathlib; pathlib.Path(".smoke/avis.pdf").write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")'
python -c 'import base64,pathlib; pathlib.Path(".smoke/photo.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="))'

# Programme public temporaire + PDF joint (jamais inventé : fichier de test)
PROG_ID=$(curl -s -X POST "$BASE/api/admin/public-content/institutional" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"category":"minefop","subcategory":"fne","title":"Vérification PDF (smoke)","description":"Fiche temporaire de vérification.","eligibility":"","url":null,"deadline":null}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
DOC_URL=$(curl -s -X POST "$BASE/api/admin/public-content/institutional/$PROG_ID/documents" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@.smoke/avis.pdf" -F "label=Avis de test" \
  | python -c "import sys,json;print(json.load(sys.stdin)['documents'][0]['url'])")
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$DOC_URL")
echo "  $([ "$code" = "200" ] && echo "OK " || echo "!! ") $code téléchargement du PDF de programme"
[ "$code" = "200" ] || FAILED=1
curl -s -o /dev/null -X DELETE "$BASE/api/admin/public-content/institutional/$PROG_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Offre temporaire + photo facultative
JOB_ID=$(curl -s -X POST "$BASE/api/admin/jobs" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Offre photo (smoke)","company":"Test","location":"Douala","sector":"Test","contract_type":"CDI","description":"x","requirements":"x","source_name":"Test","source_url":"https://example.test/offre","required_skills":[]}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/admin/jobs/$JOB_ID/photo" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -F "file=@.smoke/photo.png")
code2=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/jobs/$JOB_ID/photo")
echo "  $([ "$code" = "200" ] && [ "$code2" = "200" ] && echo "OK " || echo "!! ") $code/$code2 photo facultative d'offre (envoi / lecture publique)"
[ "$code" = "200" ] && [ "$code2" = "200" ] || FAILED=1
curl -s -o /dev/null -X DELETE "$BASE/api/admin/jobs/$JOB_ID" -H "Authorization: Bearer $ADMIN_TOKEN"

echo ""
if [ -n "$FAILED" ]; then
  echo "=== ÉCHEC : au moins un endpoint a échoué ==="
  exit 1
fi
echo "=== Vérification réussie (base et serveurs utilisateur intacts) ==="
