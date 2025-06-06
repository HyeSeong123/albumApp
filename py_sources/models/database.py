import sqlite3
from pathlib import Path

class DatabaseInitializer:
    def __init__(self, db_path: str = 'album.db'):
        self.db_path = Path(db_path)
        self.connection = None
        self.cursor = None

    def initialize_database(self) -> None:
        """
        데이터베이스를 초기화하고 필요한 테이블들을 생성합니다.
        """
        self._connect()
        self._create_tables()
        self._disconnect()

    def _connect(self) -> None:
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.cursor = self.connection.cursor()
        except Exception as e:
            print(f"데이터베이스 연결 오류: {e}")
            raise

    def _disconnect(self) -> None:
        """데이터베이스 연결을 종료합니다."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def _create_tables(self) -> None:
        """필요한 테이블들을 생성합니다."""
        self._create_album_table()
        self._create_photo_table()
        self._create_photo_keyword_table()

    def _create_album_table(self) -> None:
        """album 테이블을 생성합니다."""
        query = '''
        CREATE TABLE IF NOT EXISTS album (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT
        )
        '''
        self.cursor.execute(query)
        self.connection.commit()

    def _create_photo_table(self) -> None:
        """photo 테이블을 생성합니다."""
        query = '''
        CREATE TABLE IF NOT EXISTS photo (
            id TEXT PRIMARY KEY,
            album_id TEXT,
            filename TEXT,
            filepath TEXT,
            width INTEGER,
            height INTEGER,
            taken_at TEXT,
            created_date TEXT,
            modified_date TEXT,
            memo TEXT,
            FOREIGN KEY (album_id) REFERENCES album(id)
        )
        '''
        self.cursor.execute(query)
        self.connection.commit()

    def _create_photo_keyword_table(self) -> None:
        """photo_keyword 테이블을 생성합니다."""
        query = '''
        CREATE TABLE IF NOT EXISTS photo_keyword (
            photo_id TEXT,
            keyword TEXT,
            PRIMARY KEY (photo_id, keyword),
            FOREIGN KEY (photo_id) REFERENCES photo(id)
        )
        '''
        self.cursor.execute(query)
        self.connection.commit()

    @staticmethod
    def initialize() -> None:
        """
        데이터베이스 초기화를 실행합니다.
        이 메서드는 프로그램 시작 시점에 한 번만 실행되어야 합니다.
        """
        initializer = DatabaseInitializer()
        initializer.initialize_database()
        print("데이터베이스 초기화가 완료되었습니다.")
