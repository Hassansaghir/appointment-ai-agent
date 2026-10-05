
from database import engine, Base
import models


def initialize_database():
    print("Connecting to SQL Server...")

    Base.metadata.create_all(bind=engine)

    print("Database tables created successfully.")

    print("Tables found:")
    for table_name in Base.metadata.tables:
        print(f"- {table_name}")


if __name__ == "__main__":
    initialize_database()