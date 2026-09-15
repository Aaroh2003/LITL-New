from .config import Settings
from .db import Database


def main():
    settings = Settings()
    settings.validate()
    db = Database(settings.database_url)
    db.setup()
    db.engine.dispose()
    print("LiTL greenfield schema v1 initialized; hosted RLS/grants hardened.")


if __name__ == "__main__":
    main()
