<?php
// data/ のJSON（GitHub Actions が転送したもの）をデータベースに取り込む。?key= 必須
// - players: 毎回全件入れ替え
// - 期ごとのデータ: 未取り込みの期と最新の期を（削除してから）取り込み直す
// - 新人リーグの結果: 投稿のステータス（入門・落選）を更新
declare(strict_types=1);
require __DIR__ . '/../lib.php';
require_key();
set_time_limit(600);

$pdo = db();
$dir = rtrim((string)config()['data_dir'], '/');
$index = read_json_file("$dir/index.json");
if (!$index) json_out(['ok' => false, 'error' => 'data/index.json がありません'], 404);
$current = (int)$index['current_season'];
$report = ['players' => 0, 'seasons' => [], 'submissions' => 0];

// ---------------- players ----------------
$players = read_json_file("$dir/players.json") ?? [];
$pdo->beginTransaction();
$pdo->exec("DELETE FROM players");
$st = $pdo->prepare("INSERT INTO players (id, name, league, retired, retired_season, age, elo, peak_elo, talent, volatility,
    params, master_id, clan_root_id, generation, games, p1, p2, p3, p4, total_points, created, submission_id, creator)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)");
foreach ($players as $p) {
    $pl = $p['placements'] ?? [0, 0, 0, 0];
    $st->execute([
        $p['id'], $p['display_name'] ?? $p['id'], !empty($p['retired']) ? null : $p['league'],
        !empty($p['retired']) ? 1 : 0, $p['retired_season'] ?? null,
        (int)$p['initial_age'] + (int)$p['total_seasons'], $p['elo'], $p['peak_elo'], $p['talent'] ?? 0,
        $p['volatility'] ?? 1, json_encode($p['params'] ?? []), $p['parent_a_id'] ?? null, $p['clan_root_id'] ?? null,
        (int)($p['generation'] ?? 0), (int)($p['games'] ?? 0), $pl[0], $pl[1], $pl[2], $pl[3],
        (float)($p['total_points'] ?? 0), !empty($p['created']) ? 1 : 0, $p['submission_id'] ?? null, $p['creator'] ?? null,
    ]);
}
$pdo->commit();
$report['players'] = count($players);

// ---------------- 期ごと ----------------
$done = array_map('intval', $pdo->query("SELECT season FROM import_log")->fetchAll(PDO::FETCH_COLUMN));
for ($s = 1; $s <= $current; $s++) {
    if (in_array($s, $done, true) && $s !== $current) continue;
    $standings = read_json_file("$dir/standings/season_$s.json");
    $matches = read_json_file("$dir/matches/season_$s.json");
    $titles = read_json_file("$dir/titles/season_$s.json");
    if ($standings === null || $matches === null) continue;

    $pdo->beginTransaction();
    foreach (["DELETE ry FROM round_yaku ry JOIN rounds r ON r.id = ry.round_id JOIN games g ON g.id = r.game_id WHERE g.season = ?",
              "DELETE rs FROM round_seats rs JOIN rounds r ON r.id = rs.round_id JOIN games g ON g.id = r.game_id WHERE g.season = ?",
              "DELETE r FROM rounds r JOIN games g ON g.id = r.game_id WHERE g.season = ?",
              "DELETE gp FROM game_players gp JOIN games g ON g.id = gp.game_id WHERE g.season = ?",
              "DELETE FROM games WHERE season = ?",
              "DELETE FROM standings WHERE season = ?",
              "DELETE FROM titles WHERE season = ?"] as $sql) {
        $pdo->prepare($sql)->execute([$s]);
    }

    $st = $pdo->prepare("INSERT INTO standings (season, league, rank_no, player_id, name, points, games, p1, p2, p3, p4, elo, movement, exempt)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)");
    foreach ($standings as $r) {
        $pl = $r['placements'];
        $st->execute([$s, $r['league'], $r['rank'], $r['id'], $r['name'], $r['points'], $r['games'],
                      $pl[0], $pl[1], $pl[2], $pl[3], $r['elo'], $r['movement'], !empty($r['exempt']) ? 1 : 0]);
    }

    $stT = $pdo->prepare("INSERT INTO titles (season, title, event, winner_id, winner_name, previous_id, previous_name) VALUES (?,?,?,?,?,?,?)");
    foreach ($titles ?? [] as $t) {
        $stT->execute([$s, $t['title'], $t['event'], $t['winner_id'], $t['winner_name'], $t['previous_id'], $t['previous_name']]);
    }

    $stG = $pdo->prepare("INSERT INTO games (id, season, kind, league, title, stage, section_no, table_no, game_no, has_kifu)
                          VALUES (?,?,?,?,?,?,?,?,?,?)");
    $stGP = $pdo->prepare("INSERT INTO game_players (game_id, seat, player_id, name, final_score, placement, points) VALUES (?,?,?,?,?,?,?)");
    $stR = $pdo->prepare("INSERT INTO rounds (game_id, idx, round_name, honba, type, winner_id, loser_id, tile, han, fu, yakuman, label, value, yaku)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)");
    $stRS = $pdo->prepare("INSERT INTO round_seats (round_id, seat, player_id, riichi, won, dealt_in, tenpai, delta) VALUES (?,?,?,?,?,?,?,?)");
    $stRY = $pdo->prepare("INSERT INTO round_yaku (round_id, name, han) VALUES (?,?,?)");
    foreach ($matches as $m) {
        $ev = $m['event'];
        $stG->execute([$m['id'], $s, $ev['kind'], $ev['league'] ?? null, $ev['title'] ?? null, $ev['stage'] ?? null,
                       $ev['section'] ?? null, $ev['table'] ?? null, (int)($ev['game'] ?? 0), !empty($m['has_kifu']) ? 1 : 0]);
        foreach ($m['seats'] as $seat => $pid) {
            $stGP->execute([$m['id'], $seat, $pid, $m['names'][$seat], $m['final_scores'][$seat], $m['placement'][$seat], $m['points'][$seat]]);
        }
        foreach ($m['rounds'] as $i => $r) {
            $win = $r['win'] ?? null;
            $winner = isset($r['winner']) && $r['winner'] !== null ? $m['seats'][$r['winner']] : null;
            $loser = isset($r['loser']) && $r['loser'] !== null ? $m['seats'][$r['loser']] : null;
            $yakuText = $win ? implode('・', array_column($win['yaku'], 0)) : null;
            $stR->execute([$m['id'], $i, $r['round'], $r['honba'], $r['type'], $winner, $loser, $r['tile'] ?? null,
                           $win['han'] ?? null, $win['fu'] ?? null, (int)($win['yakuman'] ?? 0), $win['label'] ?? null,
                           $win['value'] ?? null, $yakuText]);
            $rid = (int)$pdo->lastInsertId();
            foreach ($m['seats'] as $seat => $pid) {
                $stRS->execute([$rid, $seat, $pid, !empty($r['riichi'][$seat]) ? 1 : 0,
                                ($r['winner'] ?? null) === $seat ? 1 : 0, ($r['loser'] ?? null) === $seat ? 1 : 0,
                                isset($r['tenpai']) ? (!empty($r['tenpai'][$seat]) ? 1 : 0) : null, (int)$r['deltas'][$seat]]);
            }
            foreach ($win['yaku'] ?? [] as $y) {
                if ($y[0] === 'ドラ') continue;
                $stRY->execute([$rid, $y[0], (int)$y[1]]);
            }
        }
    }
    $pdo->prepare("REPLACE INTO import_log (season, imported_at) VALUES (?, NOW())")->execute([$s]);
    $pdo->commit();
    $report['seasons'][] = $s;
}

// ---------------- 新人リーグの結果 → 投稿ステータス ----------------
$byId = [];
foreach ($players as $p) if (!empty($p['submission_id'])) $byId[(int)$p['submission_id']] = $p['id'];
$st = $pdo->prepare("UPDATE submissions SET status = ?, target_season = ?, result_rank = ?, player_id = ? WHERE id = ? AND status <> 'entered'");
foreach (glob("$dir/newcomer_league/for_season_*.json") ?: [] as $file) {
    $nl = read_json_file($file);
    foreach ($nl['standings'] ?? [] as $row) {
        if (empty($row['submission_id'])) continue;
        $sid = (int)$row['submission_id'];
        $st->execute([$row['winner'] ? 'entered' : 'not_selected', $nl['season'], $row['rank'], $byId[$sid] ?? null, $sid]);
        $report['submissions'] += $st->rowCount();
    }
}
json_out(['ok' => true] + $report);
