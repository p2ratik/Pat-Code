import sqlite3
from dataclasses import dataclass
from pathlib import Path
from config.loader import get_config_dir
import json

DB_LOGS = "logs"

@dataclass
class Columns:
    session_id : str
    role : str 
    content : str | None = None
    token : int = 0
    tool_calls : str | None = None
    tool_call_id : str | None = None
    

class DataBaseManager():

    def __init__(self):
        self.file_path : Path | None = get_config_dir() / DB_LOGS
        self._connection = self._get_connection()
        self._initiliaze_db()

    def _get_connection(self):
        try:
            return sqlite3.connect(self.file_path)
        except Exception as e:
            print(f"Error {e}")
            raise

    def _initiliaze_db(self):
        query = """
        CREATE TABLE IF NOT EXISTS session_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            token INTEGER,
            tool_calls TEXT,
            tool_call_id TEXT,
            time DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """
        # Have to add indexing on session_id
        try:
            with self._connection:
                self._connection.execute(query)
        except Exception as e:
            print("Error while creating db")
            raise

    def add_msg_to_db(self, columns : Columns)-> None:
        query = "INSERT INTO session_logs (session_id , role, content , token ,tool_calls, tool_call_id) VALUES (?, ?, ?, ?, ?, ?)"

        try:
            with self._connection:
                self._connection.execute(query, (columns.session_id, columns.role, columns.content, columns.token, columns.tool_calls, columns.tool_call_id))
                self._connection.commit()
        except Exception as e:
            print(f"Cant add User Message to logs db !! {e}") 
        # finally:
        #     self._connection.close()    






        
        
        
        


