"""Create ledger schema and secondary indexes on the target database."""

from app.main import Base, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("LedgerHA schema ready (orders + indexes).")


if __name__ == "__main__":
    main()
