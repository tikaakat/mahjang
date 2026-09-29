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

set_exception_handler(function (Throwable $e) {
    // 詳細はサーバーのエラーログへ。応答には原因の種類だけを返す（パスワード等を出さない）
    error_log('[mahjong] ' . $e);
    $msg = $e instanceof PDOException ? 'データベースに接続できないか、SQLでエラーが発生しました（config.php の接続情報を確認してください）'
                                      : 'サーバー内部でエラーが発生しました';
    $out = ['ok' => false, 'error' => $msg];
    // キー付きで呼ばれる管理用ページでは、原因の特定のため詳細も返す（パスワードは含まれない）
    if (defined('SHOW_ERROR_DETAIL')) {
        $out['detail'] = $e->getMessage();
    }
    json_out($out, 500);
});

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
    if (PHP_SAPI === 'cli') {
        // SSH から php コマンドで実行された場合（GitHub Actions）。失敗は終了コードで伝える
        echo json_encode($data, JSON_UNESCAPED_UNICODE), "\n";
        exit($status >= 400 ? 1 : 0);
    }
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

function require_key(): void {
    // サーバー上で直接実行された場合（SSH 経由の php コマンド）はキー不要。詳細なエラーも返す
    if (PHP_SAPI === 'cli') {
        if (!defined('SHOW_ERROR_DETAIL')) {
            define('SHOW_ERROR_DETAIL', true);
        }
        return;
    }
    $key = (string)($_GET['key'] ?? '');
    if ($key === '' || !hash_equals((string)config()['secret_key'], $key)) {
        json_out(['ok' => false, 'error' => 'forbidden'], 403);
    }
    if (!defined('SHOW_ERROR_DETAIL')) {
        define('SHOW_ERROR_DETAIL', true);
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
