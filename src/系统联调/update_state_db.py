#!/usr/bin/env python3
"""
更新状态库，添加故障诊断案例
"""

import sqlite3
import datetime
import sys

def update_state_db():
    """更新状态库"""
    db_path = "data/shared_state/state.db"
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查learned_concepts表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='learned_concepts'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("错误: learned_concepts表不存在")
            conn.close()
            return False
        
        # 要插入的故障诊断概念
        fault_concepts = [
            {
                "concept_id": "sensor_out_of_range_diagnosis",
                "title": "传感器数据越界故障诊断",
                "category": "故障诊断",
                "learned_date": datetime.date.today().isoformat()
            },
            {
                "concept_id": "serial_communication_failure_diagnosis",
                "title": "串口通信故障诊断",
                "category": "故障诊断",
                "learned_date": datetime.date.today().isoformat()
            },
            {
                "concept_id": "actuator_stall_diagnosis",
                "title": "执行器堵转故障诊断",
                "category": "故障诊断",
                "learned_date": datetime.date.today().isoformat()
            },
            {
                "concept_id": "data_sync_delay_diagnosis",
                "title": "数据同步延迟故障诊断",
                "category": "故障诊断",
                "learned_date": datetime.date.today().isoformat()
            },
            {
                "concept_id": "system_integration_testing",
                "title": "系统集成测试方法论",
                "category": "测试方法",
                "learned_date": datetime.date.today().isoformat()
            }
        ]
        
        # 插入数据（使用INSERT OR IGNORE避免重复）
        inserted_count = 0
        for concept in fault_concepts:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO learned_concepts 
                    (concept_id, title, category, learned_date)
                    VALUES (?, ?, ?, ?)
                """, (
                    concept["concept_id"],
                    concept["title"],
                    concept["category"],
                    concept["learned_date"]
                ))
                
                if cursor.rowcount > 0:
                    inserted_count += 1
                    print(f"添加概念: {concept['title']}")
                else:
                    print(f"概念已存在: {concept['title']}")
                    
            except sqlite3.Error as e:
                print(f"插入概念失败 {concept['title']}: {e}")
        
        # 提交事务
        conn.commit()
        
        # 查询当前概念总数
        cursor.execute("SELECT COUNT(*) FROM learned_concepts")
        total_count = cursor.fetchone()[0]
        
        print(f"\n状态库更新完成:")
        print(f"- 新增概念: {inserted_count} 个")
        print(f"- 总概念数: {total_count} 个")
        
        # 显示最新的概念
        cursor.execute("""
            SELECT concept_id, title, category, learned_date
            FROM learned_concepts
            ORDER BY learned_date DESC
            LIMIT 5
        """)
        
        print("\n最新5个概念:")
        print("-" * 60)
        for row in cursor.fetchall():
            print(f"ID: {row[0]}")
            print(f"标题: {row[1]}")
            print(f"分类: {row[2]}")
            print(f"学习日期: {row[3]}")
            print("-" * 60)
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False
    except Exception as e:
        print(f"未知错误: {e}")
        return False

if __name__ == "__main__":
    success = update_state_db()
    sys.exit(0 if success else 1)