from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# load environment variables from .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///clinic.db")
engine = create_engine(DATABASE_URL, future=True)


def run_sql_file(path: str):
    """Run each SQL statement from a .sql file against the DB"""
    with engine.begin() as conn:
        with open(path, "r", encoding="utf-8") as f:
            sql = f.read()
            # Split on semicolons and execute non-empty parts
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
