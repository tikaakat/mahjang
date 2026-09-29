<?php
// 最近の投稿と、新人リーグの結果（入門・落選）
declare(strict_types=1);
require __DIR__ . '/../lib.php';

$rows = db()->query("SELECT s.id, s.name, s.creator, s.type, s.status, s.target_season, s.result_rank, s.player_id,
                            DATE_FORMAT(s.created_at, '%Y-%m-%d %H:%i') AS created_at
                     FROM submissions s ORDER BY s.id DESC LIMIT 100")->fetchAll();
json_out(['ok' => true, 'submissions' => $rows]);
