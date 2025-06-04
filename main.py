from py_sources import create_app
from py_sources.models.database import DatabaseInitializer

# 데이터베이스 초기화 실행
DatabaseInitializer.initialize()
app = create_app()

if __name__ == "__main__":
    app.run(port=8080, debug=True)