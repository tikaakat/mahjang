<?php
// このファイルを config.php にコピーして値を設定する（config.php はリポジトリに含めない）
return [
    'db_dsn'  => 'mysql:host=localhost;dbname=xxxx_mahjong;charset=utf8mb4',
    'db_user' => 'xxxx_mahjong',
    'db_pass' => 'change-me',
    // GitHub Actions のシークレット IMPORT_SECRET_KEY と同じ値
    'secret_key' => 'change-me-long-random-string',
    // run_season.py が出力し、Actions が転送する data/ ディレクトリ
    'data_dir' => __DIR__ . '/data',
    // 投稿の制限
    'submit_per_ip_per_day' => 3,
    'submit_per_day' => 60,
];
