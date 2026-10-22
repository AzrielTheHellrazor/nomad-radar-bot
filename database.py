import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional
from models import TravelMode, UserSettings


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    chat_id INTEGER PRIMARY KEY,
                    active_mode TEXT NOT NULL DEFAULT 'both',
                    solo_max_budget_eur REAL NOT NULL DEFAULT 220.0,
                    couple_max_budget_eur REAL NOT NULL DEFAULT 550.0,
                    solo_watchlist TEXT NOT NULL,
                    couple_watchlist TEXT NOT NULL,
                    solo_visas TEXT NOT NULL DEFAULT '[]',
                    couple_visas TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notified_deals (
                    deal_key TEXT PRIMARY KEY,
                    last_price_eur REAL NOT NULL,
                    notified_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_user_settings(self, chat_id: int) -> UserSettings:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_settings WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            if not row:
                defaults = UserSettings(chat_id=chat_id)
                conn.execute(
                    """
                    INSERT INTO user_settings (
                        chat_id, active_mode, solo_max_budget_eur, couple_max_budget_eur,
                        solo_watchlist, couple_watchlist, solo_visas, couple_visas
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chat_id,
                        defaults.active_mode.value,
                        defaults.solo_max_budget_eur,
                        defaults.couple_max_budget_eur,
                        json.dumps(defaults.solo_watchlist),
                        json.dumps(defaults.couple_watchlist),
                        json.dumps(defaults.solo_visas),
                        json.dumps(defaults.couple_visas),
                    ),
                )
                conn.commit()
                return defaults

            return UserSettings(
                chat_id=row["chat_id"],
                active_mode=TravelMode(row["active_mode"]),
                solo_max_budget_eur=float(row["solo_max_budget_eur"]),
                couple_max_budget_eur=float(row["couple_max_budget_eur"]),
                solo_watchlist=json.loads(row["solo_watchlist"]),
                couple_watchlist=json.loads(row["couple_watchlist"]),
                solo_visas=json.loads(row["solo_visas"]),
                couple_visas=json.loads(row["couple_visas"]),
            )

    def get_all_users(self) -> List[UserSettings]:
        with self._connect() as conn:
            rows = conn.execute("SELECT chat_id FROM user_settings").fetchall()
            return [self.get_user_settings(r["chat_id"]) for r in rows]

    def set_active_mode(self, chat_id: int, mode: TravelMode) -> UserSettings:
        _ = self.get_user_settings(chat_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_settings SET active_mode = ? WHERE chat_id = ?",
                (mode.value, chat_id),
            )
            conn.commit()
        return self.get_user_settings(chat_id)

    def set_budget(self, chat_id: int, mode: TravelMode, budget_eur: float) -> UserSettings:
        _ = self.get_user_settings(chat_id)
        col = "couple_max_budget_eur" if mode == TravelMode.COUPLE else "solo_max_budget_eur"
        with self._connect() as conn:
            conn.execute(
                f"UPDATE user_settings SET {col} = ? WHERE chat_id = ?",
                (budget_eur, chat_id),
            )
            conn.commit()
        return self.get_user_settings(chat_id)

    def add_destination(self, chat_id: int, mode: TravelMode, country_code: str) -> UserSettings:
        settings = self.get_user_settings(chat_id)
        code = country_code.upper().strip()
        target_list = settings.couple_watchlist if mode == TravelMode.COUPLE else settings.solo_watchlist
        col = "couple_watchlist" if mode == TravelMode.COUPLE else "solo_watchlist"
        if code not in target_list:
            target_list.append(code)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE user_settings SET {col} = ? WHERE chat_id = ?",
                    (json.dumps(target_list), chat_id),
                )
                conn.commit()
        return self.get_user_settings(chat_id)

    def remove_destination(self, chat_id: int, mode: TravelMode, country_code: str) -> UserSettings:
        settings = self.get_user_settings(chat_id)
        code = country_code.upper().strip()
        target_list = settings.couple_watchlist if mode == TravelMode.COUPLE else settings.solo_watchlist
        col = "couple_watchlist" if mode == TravelMode.COUPLE else "solo_watchlist"
        if code in target_list:
            target_list.remove(code)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE user_settings SET {col} = ? WHERE chat_id = ?",
                    (json.dumps(target_list), chat_id),
                )
                conn.commit()
        return self.get_user_settings(chat_id)

    def add_visa(self, chat_id: int, mode: TravelMode, visa_code: str) -> UserSettings:
        settings = self.get_user_settings(chat_id)
        code = visa_code.upper().strip()
        target_list = settings.couple_visas if mode == TravelMode.COUPLE else settings.solo_visas
        col = "couple_visas" if mode == TravelMode.COUPLE else "solo_visas"
        if code not in target_list:
            target_list.append(code)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE user_settings SET {col} = ? WHERE chat_id = ?",
                    (json.dumps(target_list), chat_id),
                )
                conn.commit()
        return self.get_user_settings(chat_id)

    def should_notify_deal(self, deal_key: str, total_price_eur: float) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_price_eur FROM notified_deals WHERE deal_key = ?",
                (deal_key,),
            ).fetchone()
            if not row:
                return True
            last_price = float(row["last_price_eur"])
            # Notify again only if the price dropped by at least 10%
            return total_price_eur <= (last_price * 0.90)

    def record_notified_deal(self, deal_key: str, total_price_eur: float) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notified_deals (deal_key, last_price_eur, notified_at)
                VALUES (?, ?, ?)
                ON CONFLICT(deal_key) DO UPDATE SET
                    last_price_eur = excluded.last_price_eur,
                    notified_at = excluded.notified_at
                """,
                (deal_key, total_price_eur, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
