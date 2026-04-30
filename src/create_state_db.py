#!/usr/bin/env python3
"""
创建状态库，初始化表结构
"""
import sqlite3
import os

def init_database():
    # 数据库路径
    db_path = "data/shared_state/state.db"
    
    # 确保目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建 learned_concepts 表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS learned_concepts (
      concept_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      category TEXT,
      learned_date TEXT NOT NULL
    );
    """)
    
    # 创建 completed_projects 表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS completed_projects (
      project_id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT,
      completed_date TEXT NOT NULL
    );
    """)
    
    # 创建 applied_jobs 表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applied_jobs (
      job_id TEXT PRIMARY KEY,
      company TEXT NOT NULL,
      position TEXT,
      applied_date TEXT NOT NULL
    );
    """)
    
    # 提交并关闭
    conn.commit()
    
    # 插入今日学习的核心概念（使用 INSERT OR IGNORE 避免重复）
    concepts = [
        ('concurrency_vs_parallelism', '并发与并行区别', '并发基础', '2026-03-24'),
        ('gil_mechanism', 'GIL工作机制与影响', 'Python并发', '2026-03-24'),
        ('asyncio_architecture', 'asyncio事件循环架构', '异步编程', '2026-03-24'),
        ('industrial_async_patterns', '工业异步数据采集模式', '工业物联网', '2026-03-24'),
        ('multiprocessing_bypass_gil', '多进程绕过GIL方案', '性能优化', '2026-03-24'),
        ('concurrent_data_structures', '并发安全数据结构', '数据结构', '2026-03-24'),
    ]
    
    cursor.executemany(
        "INSERT OR IGNORE INTO learned_concepts VALUES (?, ?, ?, ?)",
        concepts
    )
    
    conn.commit()
    conn.close()
    
    print(f"状态库初始化完成：{db_path}")
    print(f"插入了 {len(concepts)} 个核心概念")

if __name__ == "__main__":
    init_database()