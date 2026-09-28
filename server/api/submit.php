<?php
// キャラクリエイトの投稿を受け付ける（POST, JSON）
declare(strict_types=1);
require __DIR__ . '/../lib.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') json_out(['ok' => false, 'error' => 'POST で送信してください'], 405);
$in = json_decode((string)file_get_contents('php://input'), true);
if (!is_array($in)) json_out(['ok' => false, 'error' => '送信内容を読み取れませんでした'], 400);
if (!empty($in['website'])) json_out(['ok' => true, 'id' => 0]);  // ボット避け（隠し項目）

$name = clean_name($in['name'] ?? '');
if ($name === null) json_out(['ok' => false, 'error' => '雀士名を入力してください'], 400);
$creator = clean_name($in['creator'] ?? '');
$type = in_array($in['type'] ?? '', PRESET_TYPES, true) ? $in['type'] : null;
$params = normalize_params($in['params'] ?? null);
if ($params === null) json_out(['ok' => false, 'error' => '打ち筋の値が不正です'], 400);

$cfg = config();
$pdo = db();
$ipHash = hash('sha256', ($_SERVER['REMOTE_ADDR'] ?? '') . '|' . $cfg['secret_key']);

$st = $pdo->prepare("SELECT COUNT(*) FROM submissions WHERE ip_hash = ? AND created_at >= NOW() - INTERVAL 1 DAY");
$st->execute([$ipHash]);
if ((int)$st->fetchColumn() >= (int)$cfg['submit_per_ip_per_day']) {
    json_out(['ok' => false, 'error' => '投稿は1日' . (int)$cfg['submit_per_ip_per_day'] . '件までです'], 429);
}
$total = (int)$pdo->query("SELECT COUNT(*) FROM submissions WHERE created_at >= NOW() - INTERVAL 1 DAY")->fetchColumn();
if ($total >= (int)$cfg['submit_per_day']) json_out(['ok' => false, 'error' => '本日の受付は締め切りました'], 429);

$st = $pdo->prepare("SELECT (SELECT COUNT(*) FROM players WHERE name = ? AND retired = 0)
                          + (SELECT COUNT(*) FROM submissions WHERE name = ? AND status IN ('pending','exported'))");
$st->execute([$name, $name]);
if ((int)$st->fetchColumn() > 0) json_out(['ok' => false, 'error' => 'その名前は使われています'], 409);

$st = $pdo->prepare("INSERT INTO submissions (name, creator, type, params, ip_hash, created_at) VALUES (?, ?, ?, ?, ?, NOW())");
$st->execute([$name, $creator, $type, json_encode($params), $ipHash]);
json_out(['ok' => true, 'id' => (int)$pdo->lastInsertId(), 'params' => $params]);
