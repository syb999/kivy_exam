import json
import sqlite3
from pathlib import Path

def migrate_from_py_to_db(py_file_path, db_path='../data/quiz.db'):
    """从Python题库文件迁移到SQLite数据库"""
    # 动态导入questions模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("questions", py_file_path)
    questions_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(questions_module)
    
    # 连接到数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 确保表存在
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        options TEXT NOT NULL,
        answer TEXT NOT NULL,
        type TEXT NOT NULL,
        score INTEGER DEFAULT 1,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    )
    ''')
    
    # 导入每个题库
    for quiz_name, questions_data in questions_module.questions.items():
        # 插入题库信息
        cursor.execute('''
        INSERT OR REPLACE INTO quizzes (name, description)
        VALUES (?, ?)
        ''', (quiz_name, f"从questions.py迁移的题库: {quiz_name}"))
        
        # 获取题库ID
        cursor.execute('SELECT id FROM quizzes WHERE name = ?', (quiz_name,))
        quiz_id = cursor.fetchone()[0]
        
        # 删除旧的题目（如果有）
        cursor.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))
        
        # 插入题目
        for q in questions_data:
            cursor.execute('''
            INSERT INTO questions (
                quiz_id, question, options, answer, type, score
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                quiz_id,
                q['question'],
                json.dumps(q['options'], ensure_ascii=False),
                json.dumps(q['answer'], ensure_ascii=False) if isinstance(q['answer'], list) else q['answer'],
                q.get('type', 'single'),
                q.get('score', 1)
            ))
    
    conn.commit()
    conn.close()
    print("题库迁移完成！")

if __name__ == '__main__':
    # 使用示例 - 假设questions.py在data目录下
    migrate_from_py_to_db('../data/questions.py')
