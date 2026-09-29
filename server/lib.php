<?php
// 共通処理（直接アクセス不可。.htaccess で拒否している）
declare(strict_types=1);

const PARAM_KEYS = ['speed_weight', 'dora_weight', 'yakuhai_weight', 'flush_weight', 'tanyao_weight',
                    'call_weight', 'riichi_weight', 'defense_weight', 'push_weight'];
// mahjong_league/creation.py と揃えること
const PARAM_MIN = 0.5;
const PARAM_MAX = 10.0;
const PARAM_BUDGET = 45.0;
const NAME_MAX_LEN = 12;
const PRESET_TYPES = ['balanced', 'attack', 'defense', 'caller', 'flush'];

function config(): array {
    static $cfg = null;
    if ($cfg === null) {
        $path = __DIR__ . '/config.php';
        if (!is_file($path)) {
            json_out(['ok' => false, 'error' => 'config.php がありません（config.sample.php をコピーして設定してください）'], 500);
        }
        $cfg = require $path;
    }
    return $cfg;
}

function db(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $c = config();
        $pdo = new PDO($c['db_dsn'], $c['db_user'], $c['db_pass'], [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]);
    }
    return $pdo;
}

function json_out($data, int $status = 200): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

function require_key(): void {
    $key = (string)($_GET['key'] ?? '');
    if ($key === '' || !hash_equals((string)config()['secret_key'], $key)) {
        json_out(['ok' => false, 'error' => 'forbidden'], 403);
    }
}

function clean_name($name): ?string {
    $name = trim(preg_replace('/[\p{C}]/u', '', (string)$name) ?? '');
    if ($name === '') return null;
    return mb_substr($name, 0, NAME_MAX_LEN);
}

/** 範囲外は切り詰め、合計が予算を超えたら比率を保って縮める。不正なら null */
function normalize_params($raw): ?array {
    if (!is_array($raw)) return null;
    $values = [];
    foreach (PARAM_KEYS as $k) {
        if (!isset($raw[$k]) || !is_numeric($raw[$k])) return null;
        $values[$k] = max(PARAM_MIN, min(PARAM_MAX, (float)$raw[$k]));
    }
    $total = array_sum($values);
    if ($total > PARAM_BUDGET) {
        $scale = PARAM_BUDGET / $total;
        foreach ($values as $k => $v) $values[$k] = max(PARAM_MIN, $v * $scale);
    }
    foreach ($values as $k => $v) $values[$k] = round($v, 3);
    return $values;
}

function read_json_file(string $path) {
    if (!is_file($path)) return null;
    return json_decode((string)file_get_contents($path), true);
}
