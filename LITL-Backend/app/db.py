from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from .models import Base


class Database:
    def __init__(self, url):
        if url.startswith("sqlite:///"):
            path = url.removeprefix("sqlite:///")
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            url, pool_pre_ping=True, hide_parameters=True,
            connect_args={"check_same_thread": False, "timeout": 15} if url.startswith("sqlite") else {},
        )
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def sqlite_setup(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def setup(self):
        if self.engine.dialect.name == "postgresql":
            # Create and harden in the same transaction: Supabase's default grants
            # must never expose newly created tables between these operations.
            with self.engine.begin() as conn:
                Base.metadata.create_all(conn)
                for table in Base.metadata.sorted_tables:
                    name = table.name
                    conn.execute(text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
                    conn.execute(text(f'REVOKE ALL ON TABLE "{name}" FROM PUBLIC, anon, authenticated'))
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION litl_immutable_update() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                      RAISE EXCEPTION 'LiTL audit records and report snapshots are immutable';
                    END $$;
                """))
                for table in ("review_events", "report_snapshots", "source_requests", "summary_review_events"):
                    conn.execute(text(f'DROP TRIGGER IF EXISTS immutable_update ON "{table}"'))
                    conn.execute(text(f"""
                        CREATE TRIGGER immutable_update BEFORE UPDATE ON "{table}"
                        FOR EACH ROW EXECUTE FUNCTION litl_immutable_update()
                    """))
        else:
            with self.engine.begin() as conn:
                Base.metadata.create_all(conn)
                for table in ("review_events", "report_snapshots", "source_requests", "summary_review_events"):
                    conn.execute(text(f"""
                        CREATE TRIGGER IF NOT EXISTS {table}_immutable BEFORE UPDATE ON {table}
                        BEGIN SELECT RAISE(ABORT, 'immutable record'); END
                    """))

    @contextmanager
    def transaction(self):
        with self.sessions() as session:
            if self.engine.dialect.name == "sqlite":
                session.execute(text("BEGIN IMMEDIATE"))
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise
