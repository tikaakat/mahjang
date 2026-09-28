<?php
// テーブル作成（何度実行しても安全）。GitHub Actions から ?key= 付きで呼ぶ
declare(strict_types=1);
require __DIR__ . '/../lib.php';
require_key();

$sql = (string)file_get_contents(__DIR__ . '/../schema.sql');
$sql = preg_replace('/^--.*$/m', '', $sql);
foreach (array_filter(array_map('trim', explode(';', $sql))) as $stmt) {
    db()->exec($stmt);
}
json_out(['ok' => true]);
