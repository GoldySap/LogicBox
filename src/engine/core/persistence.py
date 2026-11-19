import copy
import json
import sqlite3
import threading
from pathlib import Path
from typing import Callable, Dict, Optional


class SaveMigration:
    def __init__(self, version: int, migrate: Callable[[dict], dict]):
        if version <= 0:
            raise ValueError("migration version must be positive")
        self.version = version
        self.migrate = migrate


class SaveSystem:
    def __init__(self, migrations: Optional[Dict[int, SaveMigration]] = None):
        self.migrations = dict(migrations or {})
        self.version = max(self.migrations, default=1)

    def migrate(self, data: dict) -> dict:
        result = copy.deepcopy(data)
        version = int(result.get("schema_version", 1))
        if version > self.version:
            raise ValueError("save data is from an unsupported future version")
        for target in range(version + 1, self.version + 1):
            migration = self.migrations.get(target)
            if migration:
                result = migration.migrate(result)
            result["schema_version"] = target
        return result

    def save_json(self, path, data: dict):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = self.migrate(data)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(destination)

    def load_json(self, path) -> dict:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("save root must be an object")
        return self.migrate(data)


class SaveDatabase:
    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.RLock()

    def execute(self, statement: str, parameters=()):
        with self._lock:
            with sqlite3.connect(self.path) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                cursor = connection.execute(statement, parameters)
                connection.commit()
                return cursor.fetchall()
