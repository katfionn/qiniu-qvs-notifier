# -*- coding: utf-8 -*-
from qiniu import QiniuMacAuth, http
import json
import os
import requests

def listNamespacesInfo(access_key, secret_key, namespaceId, gbId):
    auth = QiniuMacAuth(access_key, secret_key)
    url = f"http://qvs.qiniuapi.com/v1/namespaces/{namespaceId}/devices/{gbId}"
    ret, res = http._get_with_qiniu_mac(url, params=None, auth=auth)
    headers = {"code": res.status_code, "reqid": res.req_id, "xlog": res.x_log, "text_body": res.text_body}
    return json.loads(ret)['result']  # 返回 "result" 字段的值

def send_webhook_message(webhook_url, message):
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        'msgtype': 'text',
        'text': {
            'content': message,
        },
    }
    response = requests.post(webhook_url, headers=headers, json=data)
    if response.status_code != 200:
        print(f'请求失败，状态码：{response.status_code}，错误信息：{response.text}')
        return False
    print(f'请求成功！')
    return True

def main():
    # 七牛账号 AK、SK
    access_key = '{{access_key}}'
    secret_key = '{{secret_key}}'

    # 空间ID
    namespaceId = "NAMESPACEID"

    # 设备国标Id
    gbId = "GBID"

    # 获取 devices.txt 文件中的数据，并替换NAMESPACEID和GBID
    with open('devices.txt', 'r') as f:
        devices = f.readlines()
    for device in devices:
        device = device.strip()  # 去除行尾的换行符
        if device:  # 如果这行不为空
            param1, param2, message = device.split(',')  # 按逗号分割参数，这里假设只有3个参数
            namespaceId = param1.strip()  # 去除行尾的换行符和空格，并赋值给NAMESPACEID
            gbId = param2.strip()  # 去除行尾的换行符和空格，并赋值给GBID
            result = listNamespacesInfo(access_key, secret_key, namespaceId, gbId)  # 使用新的函数调用并获取结果
            if result['state'] == 'online':  # 根据返回结果中的 "state" 字段判断消息内容
                webhook_url = 'https://oapi.dingtalk.com/robot/send?access_token=your_dingding_webhook_url'  # 钉钉机器人的webhook地址
                send_webhook_message(webhook_url, f'"{message}"设备在线')  # 发送消息给钉钉机器人，
            if result['state'] == 'offline':  # 根据返回结果中的 "state" 字段判断消息内容
                webhook_url = 'https://oapi.dingtalk.com/robot/send?access_token=your_dingding_webhook_url'  # 钉钉机器人的webhook地址
                send_webhook_message(webhook_url, f'"{message}"设备离线')  # 发送消息给钉钉机器人，