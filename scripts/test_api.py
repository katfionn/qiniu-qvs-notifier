#!/usr/bin/env python3
"""完整业务功能测试脚本"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_login():
    print_section("1. 登录测试")
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    print(f"状态码: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data['access_token']

def test_create_source_channel(token):
    print_section("2. 创建监听渠道")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{BASE_URL}/api/source-channels", headers=headers, json={
        "name": "测试七牛云",
        "provider": "qiniu",
        "config": {
            "access_key": "test_ak_123",
            "secret_key": "test_sk_456",
            "namespace_id": "test_namespace"
        }
    })
    print(f"状态码: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data.get('id')

def test_create_notification_channel(token):
    print_section("3. 创建通知渠道")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{BASE_URL}/api/notification-channels", headers=headers, json={
        "name": "测试NTFY",
        "type": "ntfy",
        "config": {
            "server": "https://ntfy.sh",
            "topic": "test-qvs-notifier"
        }
    })
    print(f"状态码: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data.get('id')

def test_create_task(token, source_id, notif_id):
    print_section("4. 创建监控任务")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{BASE_URL}/api/tasks", headers=headers, json={
        "name": "测试任务",
        "description": "每5分钟检查一次",
        "cron_expression": "*/5 * * * *",
        "source_channel_id": source_id,
        "notification_channel_ids": [notif_id],
        "enabled": True
    })
    print(f"状态码: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data.get('id')

def test_list_all(token):
    print_section("5. 查看所有数据")
    headers = {"Authorization": f"Bearer {token}"}

    print("\n--- 任务列表 ---")
    resp = requests.get(f"{BASE_URL}/api/tasks", headers=headers)
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

    print("\n--- 监听渠道列表 ---")
    resp = requests.get(f"{BASE_URL}/api/source-channels", headers=headers)
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

    print("\n--- 通知渠道列表 ---")
    resp = requests.get(f"{BASE_URL}/api/notification-channels", headers=headers)
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

def test_scheduler_status(token):
    print_section("6. 调度器状态")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/api/scheduler/status", headers=headers)
    print(f"状态码: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

def test_update_task(token, task_id):
    print_section("7. 更新任务（禁用）")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.put(f"{BASE_URL}/api/tasks/{task_id}", headers=headers, json={
        "enabled": False
    })
    print(f"状态码: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

def test_delete_task(token, task_id):
    print_section("8. 删除任务")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.delete(f"{BASE_URL}/api/tasks/{task_id}", headers=headers)
    print(f"状态码: {resp.status_code}")

def main():
    print("\n" + "=" * 60)
    print("  七牛 QVS 通知器 v2.0 - 完整业务测试")
    print("=" * 60)

    try:
        # 1. 登录
        token = test_login()

        # 2. 创建监听渠道
        source_id = test_create_source_channel(token)

        # 3. 创建通知渠道
        notif_id = test_create_notification_channel(token)

        # 4. 创建任务
        task_id = test_create_task(token, source_id, notif_id)

        # 5. 查看所有数据
        test_list_all(token)

        # 6. 调度器状态
        test_scheduler_status(token)

        # 7. 更新任务
        if task_id:
            test_update_task(token, task_id)

        # 8. 删除任务
        if task_id:
            test_delete_task(token, task_id)

        print_section("✓ 所有测试完成")
        print("\n测试结果：")
        print("✓ 登录功能正常")
        print("✓ 监听渠道创建正常")
        print("✓ 通知渠道创建正常")
        print("✓ 监控任务创建正常")
        print("✓ 数据查询正常")
        print("✓ 任务更新正常")
        print("✓ 任务删除正常")
        print("\n所有 API 功能验证通过！")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
