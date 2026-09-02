# -*- coding: utf-8 -*-
from qiniu import QiniuMacAuth, http
import json
import sys
import re
import requests
import logging
import os
#import pytz  #第三版的日志记录之日期转换UTC格式
from datetime import datetime
#import time #用于主函数循环里每次循环结束后添加等待，对应下面的time.sleep(1)

# 设置日志文件路径和文件名
LOG_FILE = 'check_online.txt'


# 创建日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#第三版的日志记录
# 创建一个UTC时区对象
#utc_tz = pytz.UTC

# 获取当前时间（UTC）
#now = datetime.datetime.now(utc_tz)

# 创建文件处理程序，将日志输出到文件
handler = logging.FileHandler('check_online.txt')
handler.setLevel(logging.INFO)

# 创建格式化器，指定日期和时间格式为YYYY-MM-DD HH:MM:SS
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)

# 将处理程序添加到日志记录器中
logger.addHandler(handler)



def send_dingtalk_message(webhook_url, state, device):
    message = f"[{device} 设备{state}]"
    headers = {
        'Content-Type': 'application/json;charset=utf-8',
    }
    data = {
        "msgtype": "text",
        "text": {
            "content": message,
        }
    }
    response = requests.post(webhook_url, headers=headers, data=json.dumps(data))
    return response.status_code == 200

def listNamespacesInfo(access_key, secret_key, namespaceId, streamId):
    auth = QiniuMacAuth(access_key, secret_key)

    # 请求URL
    #url = f"http://qvs.qiniuapi.com/v1/namespaces/{namespaceId}/devices/{gbId}"
    url = f"http://qvs.qiniuapi.com/v1/namespaces/{namespaceId}/streams/{streamId}/enabled"

    # 发起GET请求
    ret, res = http._get_with_qiniu_mac(url, params=None, auth=auth)
    headers = {"code": res.status_code, "reqid": res.req_id, "xlog": res.x_log, "text_body": res.text_body}

    # 格式化响应体
    Headers = json.dumps(headers, indent=4, ensure_ascii=False)
    result = json.dumps(ret, indent=4, ensure_ascii=False)
    return Headers, result




if __name__ == '__main__':
    #  AKSK
    access_key = '{{access_key}}'
    secret_key = '{{secret_key}}'

    with open('devices.txt', 'r') as file:
        for line in file:
            # 解析参数1、参数2
            param1, param2 = line.strip().split(':')
            # 执行函数
            headers, result = listNamespacesInfo(access_key, secret_key, param1, param2)

                # 解析result中的"state"参数值
            #code = json.loads(result)['code']

            # 判断"state"参数值并发送webhook消息
            #if code == '200':
            #    device = param3
            #    print(f'启用成功')
                #else:
                    #print(f'发送[设备{device} 在线]消息到钉钉机器人失败。')
            #elif code != '200':
            #    print(f'启用失败')
            #else:
            #    print(f'无效的state值：{state}')
            print(f'执行成功')
            # 输出结果
            #print(f'Namespace: {param1}, GBID: {param2}, Device: {param3}')
            #print(f'{headers}\n{result}')
            # 记录日志到文件(第一版)
            #log_message = f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} {device} state: {state}\n'
            #with open(LOG_FILE, 'a', encoding='utf-8') as logfile:logfile.write(log_message)


            # 在记录日志时，使用logger对象代替print函数  （第二版）
            #logger.info(f'设备 {device} 状态：{state}')
            #time.sleep(1) #本用来每次请求接口后等待一下，防止高频请求，现在不需要了

            # 使用logger记录日志信息
            #logger.info(f'设备 {device} 状态：{state}')
            #logger.info(f'当前时间：{now.strftime("%Y-%m-%d %H:%M:%S")}')
