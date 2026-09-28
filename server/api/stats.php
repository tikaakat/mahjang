<?php
// 集計API。?type=players|yakuman|big_hands|yaku|titles|clans|scores （任意: season, league, min_hands）
declare(strict_types=1);
require __DIR__ . '/../lib.php';

$type = (string)($_GET['type'] ?? 'players');
$season = isset($_GET['season']) && $_GET['season'] !== '' ? (int)$_GET['season'] : null;
$pdo = db();
$seasonCond = $season !== null ? ' AND g.season = :season' : '';
$bind = $season !== null ? [':season' => $season] : [];
$seasonCond2 = $season !== null ? ' AND g.season = :season2' : '';  // 同じ名前のプレースホルダは2回使えないため

function q(PDO $pdo, string $sql, array $bind = []): array {
    $st = $pdo->prepare($sql);
    $st->execute($bind);
    return $st->fetchAll();
}

switch ($type) {
    case 'players':
        // 和了率・放銃率・リーチ率・平均打点・平均着順など（局単位・半荘単位）
        $minHands = max(0, (int)($_GET['min_hands'] ?? 50));
        $league = preg_match('/^[ABCD]$/', (string)($_GET['league'] ?? '')) ? $_GET['league'] : null;
        $sql = "SELECT p.id, p.name, p.league, p.retired, h.hands, h.wins, h.dealins, h.riichis, h.tsumos,
                       h.avg_value, h.max_value, g.games, g.p1, g.p2, g.p3, g.p4, g.points, g.avg_score
                FROM players p
                JOIN (SELECT rs.player_id, COUNT(*) AS hands, SUM(rs.won) AS wins, SUM(rs.dealt_in) AS dealins,
                             SUM(rs.riichi) AS riichis, SUM(rs.won AND r.type = 'tsumo') AS tsumos,
                             ROUND(AVG(CASE WHEN rs.won THEN r.value END)) AS avg_value,
                             MAX(CASE WHEN rs.won THEN r.value END) AS max_value
                      FROM round_seats rs JOIN rounds r ON r.id = rs.round_id JOIN games g ON g.id = r.game_id
                      WHERE 1=1 $seasonCond GROUP BY rs.player_id) h ON h.player_id = p.id
                JOIN (SELECT gp.player_id, COUNT(*) AS games, SUM(gp.placement = 1) AS p1, SUM(gp.placement = 2) AS p2,
                             SUM(gp.placement = 3) AS p3, SUM(gp.placement = 4) AS p4, ROUND(SUM(gp.points), 1) AS points,
                             ROUND(AVG(gp.final_score)) AS avg_score
                      FROM game_players gp JOIN games g ON g.id = gp.game_id
                      WHERE 1=1 $seasonCond2 GROUP BY gp.player_id) g ON g.player_id = p.id
                WHERE h.hands >= :min_hands" . ($league ? " AND p.league = :league" : "");
        $b = $bind + [':min_hands' => $minHands] + ($league ? [':league' => $league] : [])
             + ($season !== null ? [':season2' => $season] : []);
        json_out(['ok' => true, 'rows' => q($pdo, $sql, $b)]);

    case 'yakuman':
        $sql = "SELECT r.game_id, g.season, g.kind, g.league, g.title, g.stage, r.round_name, r.type, r.yaku, r.value,
                       r.winner_id, pw.name AS winner_name, r.loser_id, pl.name AS loser_name, g.has_kifu
                FROM rounds r JOIN games g ON g.id = r.game_id
                LEFT JOIN players pw ON pw.id = r.winner_id LEFT JOIN players pl ON pl.id = r.loser_id
                WHERE r.yakuman > 0 $seasonCond ORDER BY g.season DESC, r.game_id DESC, r.idx DESC LIMIT 300";
        json_out(['ok' => true, 'rows' => q($pdo, $sql, $bind)]);

    case 'big_hands':
        $sql = "SELECT r.game_id, g.season, g.kind, g.league, g.title, r.round_name, r.type, r.label, r.han, r.fu,
                       r.yaku, r.value, r.winner_id, pw.name AS winner_name, pl.name AS loser_name
                FROM rounds r JOIN games g ON g.id = r.game_id
                LEFT JOIN players pw ON pw.id = r.winner_id LEFT JOIN players pl ON pl.id = r.loser_id
                WHERE r.value IS NOT NULL AND r.yakuman = 0 $seasonCond ORDER BY r.value DESC, r.han DESC LIMIT 100";
        json_out(['ok' => true, 'rows' => q($pdo, $sql, $bind)]);

    case 'yaku':
        $total = q($pdo, "SELECT COUNT(*) AS n FROM rounds r JOIN games g ON g.id = r.game_id
                          WHERE r.winner_id IS NOT NULL $seasonCond", $bind)[0]['n'];
        $rows = q($pdo, "SELECT ry.name, COUNT(*) AS n FROM round_yaku ry JOIN rounds r ON r.id = ry.round_id
                         JOIN games g ON g.id = r.game_id WHERE 1=1 $seasonCond GROUP BY ry.name ORDER BY n DESC", $bind);
        json_out(['ok' => true, 'wins' => (int)$total, 'rows' => $rows]);

    case 'titles':
        $sql = "SELECT t.winner_id AS id, p.name, p.retired, t.title, COUNT(*) AS n
                FROM titles t LEFT JOIN players p ON p.id = t.winner_id GROUP BY t.winner_id, p.name, p.retired, t.title";
        json_out(['ok' => true, 'rows' => q($pdo, $sql)]);

    case 'clans':
        $sql = "SELECT p.clan_root_id AS root, f.name AS founder, COUNT(*) AS members, SUM(p.retired = 0) AS active,
                       MAX(p.peak_elo) AS best_elo, COALESCE(SUM(tc.n), 0) AS titles
                FROM players p LEFT JOIN players f ON f.id = p.clan_root_id
                LEFT JOIN (SELECT winner_id, COUNT(*) AS n FROM titles GROUP BY winner_id) tc ON tc.winner_id = p.id
                GROUP BY p.clan_root_id, f.name ORDER BY titles DESC, active DESC LIMIT 100";
        json_out(['ok' => true, 'rows' => q($pdo, $sql)]);

    case 'scores':
        // 1半荘の最高得点・最低得点
        $base = "SELECT gp.game_id, g.season, g.kind, g.league, g.title, gp.player_id, gp.name, gp.final_score, gp.placement
                 FROM game_players gp JOIN games g ON g.id = gp.game_id WHERE 1=1 $seasonCond";
        json_out(['ok' => true, 'high' => q($pdo, "$base ORDER BY gp.final_score DESC LIMIT 30", $bind),
                  'low' => q($pdo, "$base ORDER BY gp.final_score ASC LIMIT 30", $bind)]);

    default:
        json_out(['ok' => false, 'error' => 'unknown type'], 400);
}
