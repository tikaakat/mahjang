-- MAHJONG LEAGUE サイト用データベース（MySQL 5.7+ / MariaDB 10.3+）
-- admin/migrate.php から実行される（CREATE TABLE IF NOT EXISTS なので何度実行しても安全）

CREATE TABLE IF NOT EXISTS players (
  id VARCHAR(32) NOT NULL PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  league CHAR(1) NULL,
  retired TINYINT NOT NULL DEFAULT 0,
  retired_season INT NULL,
  age INT NOT NULL,
  elo DOUBLE NOT NULL,
  peak_elo DOUBLE NOT NULL,
  talent DOUBLE NOT NULL,
  volatility DOUBLE NOT NULL,
  params TEXT NOT NULL,
  master_id VARCHAR(32) NULL,
  clan_root_id VARCHAR(32) NULL,
  generation INT NOT NULL DEFAULT 0,
  games INT NOT NULL DEFAULT 0,
  p1 INT NOT NULL DEFAULT 0, p2 INT NOT NULL DEFAULT 0, p3 INT NOT NULL DEFAULT 0, p4 INT NOT NULL DEFAULT 0,
  total_points DOUBLE NOT NULL DEFAULT 0,
  created TINYINT NOT NULL DEFAULT 0,
  submission_id INT NULL,
  creator VARCHAR(64) NULL,
  KEY idx_players_name (name),
  KEY idx_players_clan (clan_root_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS standings (
  season INT NOT NULL,
  league CHAR(1) NOT NULL,
  rank_no INT NULL,
  player_id VARCHAR(32) NOT NULL,
  name VARCHAR(64) NOT NULL,
  points DOUBLE NOT NULL,
  games INT NOT NULL,
  p1 INT NOT NULL, p2 INT NOT NULL, p3 INT NOT NULL, p4 INT NOT NULL,
  elo DOUBLE NOT NULL,
  movement VARCHAR(16) NOT NULL,
  exempt TINYINT NOT NULL DEFAULT 0,
  PRIMARY KEY (season, league, player_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS games (
  id VARCHAR(16) NOT NULL PRIMARY KEY,
  season INT NOT NULL,
  kind VARCHAR(16) NOT NULL,          -- league / title
  league CHAR(1) NULL,
  title VARCHAR(16) NULL,
  stage VARCHAR(32) NULL,
  section_no INT NULL,
  table_no INT NULL,
  game_no INT NOT NULL,
  has_kifu TINYINT NOT NULL DEFAULT 0,
  KEY idx_games_season (season)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS game_players (
  game_id VARCHAR(16) NOT NULL,
  seat TINYINT NOT NULL,
  player_id VARCHAR(32) NOT NULL,
  name VARCHAR(64) NOT NULL,
  final_score INT NOT NULL,
  placement TINYINT NOT NULL,
  points DOUBLE NOT NULL,
  PRIMARY KEY (game_id, seat),
  KEY idx_gp_player (player_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS rounds (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  game_id VARCHAR(16) NOT NULL,
  idx INT NOT NULL,
  round_name VARCHAR(16) NOT NULL,
  honba INT NOT NULL,
  type VARCHAR(16) NOT NULL,          -- ron / tsumo / draw / nagashi
  winner_id VARCHAR(32) NULL,
  loser_id VARCHAR(32) NULL,
  tile INT NULL,
  han INT NULL,
  fu INT NULL,
  yakuman INT NOT NULL DEFAULT 0,
  label VARCHAR(32) NULL,
  value INT NULL,                     -- 和了打点（本場・供託を除く）
  yaku VARCHAR(255) NULL,
  UNIQUE KEY uq_rounds (game_id, idx),
  KEY idx_rounds_value (value),
  KEY idx_rounds_yakuman (yakuman)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS round_seats (
  round_id BIGINT NOT NULL,
  seat TINYINT NOT NULL,
  player_id VARCHAR(32) NOT NULL,
  riichi TINYINT NOT NULL DEFAULT 0,
  won TINYINT NOT NULL DEFAULT 0,
  dealt_in TINYINT NOT NULL DEFAULT 0,
  tenpai TINYINT NULL,
  delta INT NOT NULL,
  PRIMARY KEY (round_id, seat),
  KEY idx_rs_player (player_id)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS round_yaku (
  round_id BIGINT NOT NULL,
  name VARCHAR(32) NOT NULL,
  han INT NOT NULL,
  KEY idx_ry_round (round_id),
  KEY idx_ry_name (name)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS titles (
  season INT NOT NULL,
  title VARCHAR(16) NOT NULL,
  event VARCHAR(8) NOT NULL,
  winner_id VARCHAR(32) NOT NULL,
  winner_name VARCHAR(64) NOT NULL,
  previous_id VARCHAR(32) NULL,
  previous_name VARCHAR(64) NULL,
  PRIMARY KEY (season, title)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS submissions (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  creator VARCHAR(64) NULL,
  type VARCHAR(16) NULL,
  params TEXT NOT NULL,
  ip_hash CHAR(64) NOT NULL,
  created_at DATETIME NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'pending',   -- pending / exported / entered / not_selected
  exported_at DATETIME NULL,
  target_season INT NULL,
  result_rank INT NULL,
  player_id VARCHAR(32) NULL,
  KEY idx_sub_status (status),
  KEY idx_sub_ip (ip_hash, created_at)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS import_log (
  season INT NOT NULL PRIMARY KEY,
  imported_at DATETIME NOT NULL
) DEFAULT CHARSET=utf8mb4;
