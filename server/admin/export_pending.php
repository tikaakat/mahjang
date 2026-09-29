<?php
// 未処理の投稿を新人リーグ用に書き出す（GitHub Actions が ?key= 付きで取得する）
// 書き出した投稿は exported になる。結果が取り込まれないまま20時間経ったものは再度書き出す
declare(strict_types=1);
require __DIR__ . '/../lib.php';
require_key();

$pdo = db();
$rows = $pdo->query("SELECT id, name, creator, type, params FROM submissions
                     WHERE status = 'pending' OR (status = 'exported' AND exported_at < NOW() - INTERVAL 20 HOUR)
                     ORDER BY id LIMIT 32")->fetchAll();
if ($rows) {
    $ids = implode(',', array_map(fn($r) => (int)$r['id'], $rows));
    $pdo->exec("UPDATE submissions SET status = 'exported', exported_at = NOW() WHERE id IN ($ids)");
}
$characters = array_map(fn($r) => [
    'submission_id' => (int)$r['id'], 'name' => $r['name'], 'creator' => $r['creator'],
    'type' => $r['type'], 'params' => json_decode($r['params'], true),
], $rows);
json_out(['ok' => true, 'characters' => $characters]);
