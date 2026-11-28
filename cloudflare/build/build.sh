#!/usr/bin/env bash
# 公開する季の時点のデータ（data/ のスナップショット）から、Cloudflare に上げる dist/ を作る。
#   1. 一時的な MySQL に表を作り、data/ を取り込む（server/admin の CLI）
#   2. 集計API（stats.php）を PHP の組み込みサーバーで動かし、全パターンを JSON に書き出す
#   3. サイト（web/）とスナップショットのデータを並べ、公開済みの季を _meta.json に書く
# 使い方: bash cloudflare/build/build.sh <dataディレクトリ> <出力ディレクトリ> <公開する季>
# 前提: MariaDB が動き、DB_HOST/DB_USER/DB_PASS/DB_NAME で接続できる。php（pdo_mysql）・python3 がある。
set -euo pipefail
DATA="$(cd "$1" && pwd)"; OUT="$2"; SEASON="$3"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB_HOST="${DB_HOST:-127.0.0.1}"; DB_NAME="${DB_NAME:-mahjong}"; DB_USER="${DB_USER:-root}"; DB_PASS="${DB_PASS:-root}"

echo "=== 1. 一時的なMySQLに取り込む ==="
SRV="$(mktemp -d)"; cp -r "$ROOT/server/." "$SRV/"
cat > "$SRV/config.php" <<PHP
<?php return ['db_dsn'=>'mysql:host=$DB_HOST;dbname=$DB_NAME;charset=utf8mb4','db_user'=>'$DB_USER','db_pass'=>'$DB_PASS',
 'secret_key'=>'build','data_dir'=>'$DATA','submit_per_ip_per_day'=>0,'submit_per_day'=>0];
PHP
mysql --skip-ssl -h "$DB_HOST" -u "$DB_USER" "-p$DB_PASS" -e "DROP DATABASE IF EXISTS \`$DB_NAME\`; CREATE DATABASE \`$DB_NAME\` CHARACTER SET utf8mb4;"
(cd "$SRV" && php admin/migrate.php && php admin/import.php)

echo "=== 2. 集計を書き出す ==="
rm -rf "$OUT"; mkdir -p "$OUT/_api/stats"
php -S 127.0.0.1:8765 -t "$SRV" >/dev/null 2>&1 &
PHP_PID=$!
sleep 2
python3 "$ROOT/cloudflare/build/export_stats.py" http://127.0.0.1:8765 "$OUT/_api/stats" "$SEASON"
kill $PHP_PID || true

echo "=== 3. ページとデータを並べる ==="
sed "s/__BUILD__/${GITHUB_SHA:-local}/g" "$ROOT/web/index.html" > "$OUT/index.html"
cp "$ROOT/web/app.js" "$ROOT/web/style.css" "$OUT/"
mkdir -p "$OUT/data" "$OUT/news"
cp "$ROOT/fan-site/index.html" "$OUT/news/index.html"
for f in index.json players.json players awards standings matches titles newcomer_league; do
  [ -e "$DATA/$f" ] && cp -r "$DATA/$f" "$OUT/data/"
done
echo "{\"published_season\": $SEASON}" > "$OUT/_meta.json"
rm -rf "$SRV"
echo "=== できあがり：$(find "$OUT" -type f | wc -l) ファイル・$(du -sh "$OUT" | cut -f1) ==="
