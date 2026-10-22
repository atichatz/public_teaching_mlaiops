#!/usr/bin/env bash
set -uo pipefail

PROJECT_ID="${PROJECT_ID:-itcs355-6688193}"
BUCKET="${BUCKET:-gs://itcs355-6688193-mlops-atichat}"
TRAINING_SA="${TRAINING_SA:-itcs355-lab5-train@${PROJECT_ID}.iam.gserviceaccount.com}"
ACTIVE_USER="$(gcloud config get-value account 2>/dev/null)"
MEMBER="serviceAccount:${TRAINING_SA}"
USER_MEMBER="user:${ACTIVE_USER}"
TARGET="${BUCKET}/itcs355/lab5/permission-test/should-fail.txt"
REPORT="reports/lab5-permission-removal.txt"

creator_removed=0
token_granted=0

export ACTIVE_USER TRAINING_SA MEMBER USER_MEMBER

cleanup() {
  if [ "$creator_removed" -eq 1 ]; then
    echo "RESTORE roles/storage.objectCreator" | tee -a "$REPORT"
    gcloud storage buckets add-iam-policy-binding "$BUCKET" \
      --member="$MEMBER" \
      --role="roles/storage.objectCreator" \
      --quiet >/dev/null || true
    creator_removed=0
  fi

  if [ "$token_granted" -eq 1 ]; then
    echo "REMOVE temporary roles/iam.serviceAccountTokenCreator" | tee -a "$REPORT"
    gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
      --member="$USER_MEMBER" \
      --role="roles/iam.serviceAccountTokenCreator" \
      --condition=None \
      --quiet >/dev/null || true
    token_granted=0
  fi

  gcloud storage rm "$TARGET" >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

: > "$REPORT"
echo "Lab 5 least-privilege failure experiment" | tee -a "$REPORT"
echo "ACTIVE_USER=$ACTIVE_USER" | tee -a "$REPORT"
echo "TRAINING_SA=$TRAINING_SA" | tee -a "$REPORT"
echo "REMOVED_PERMISSION=storage.objects.create" | tee -a "$REPORT"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="$USER_MEMBER" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --condition=None \
  --quiet >/dev/null || {
    echo "FAIL could not grant temporary impersonation permission" | tee -a "$REPORT"
    exit 1
  }
token_granted=1

token_ready=0
for attempt in $(seq 1 18); do
  if gcloud --impersonate-service-account="$TRAINING_SA" \
    auth print-access-token >/dev/null 2>&1; then
    token_ready=1
    break
  fi
  echo "Waiting for temporary impersonation permission ($attempt/18)..." | tee -a "$REPORT"
  sleep 10
done

if [ "$token_ready" -ne 1 ]; then
  echo "FAIL temporary impersonation permission did not propagate" | tee -a "$REPORT"
  exit 1
fi

gcloud storage buckets remove-iam-policy-binding "$BUCKET" \
  --member="$MEMBER" \
  --role="roles/storage.objectCreator" \
  --quiet >/dev/null || {
    echo "FAIL could not remove objectCreator" | tee -a "$REPORT"
    exit 1
  }
creator_removed=1

printf '%s\n' "permission probe" > /tmp/lab5-permission-probe.txt

gcloud --impersonate-service-account="$TRAINING_SA" \
  storage cp /tmp/lab5-permission-probe.txt "$TARGET" \
  2>&1 | tee -a "$REPORT"
upload_status=${PIPESTATUS[0]}
echo "UPLOAD_EXIT_CODE=$upload_status" | tee -a "$REPORT"

if [ "$upload_status" -eq 0 ]; then
  echo "FAIL upload unexpectedly succeeded" | tee -a "$REPORT"
  exit 1
fi

if ! grep -q "storage.objects.create" "$REPORT"; then
  echo "FAIL request was blocked before the intended Storage permission check" | tee -a "$REPORT"
  exit 1
fi

cleanup
trap - EXIT INT TERM

restored_roles="$(gcloud storage buckets get-iam-policy "$BUCKET" --format=json \
  | python -c 'import json,os,sys; d=json.load(sys.stdin); m=os.environ["MEMBER"]; print("\n".join(sorted(b["role"] for b in d.get("bindings", []) if m in b.get("members", []))))')"
printf 'RESTORED_ROLES=%s\n' "$(echo "$restored_roles" | tr '\n' ',')" | tee -a "$REPORT"

temporary_role="$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json \
  | python -c 'import json,os,sys; d=json.load(sys.stdin); m=os.environ["USER_MEMBER"]; print("\n".join(b["role"] for b in d.get("bindings", []) if b.get("role") == "roles/iam.serviceAccountTokenCreator" and m in b.get("members", [])))')"

if ! echo "$restored_roles" | grep -q '^roles/storage.objectCreator$'; then
  echo "FAIL objectCreator was not restored" | tee -a "$REPORT"
  exit 1
fi

if [ -n "$temporary_role" ]; then
  echo "FAIL temporary impersonation permission remains" | tee -a "$REPORT"
  exit 1
fi

echo "PASS storage.objects.create removal blocked artifact creation" | tee -a "$REPORT"
echo "PASS original bucket access restored" | tee -a "$REPORT"
echo "PASS temporary impersonation permission removed" | tee -a "$REPORT"
