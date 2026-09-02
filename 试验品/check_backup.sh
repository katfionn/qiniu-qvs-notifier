#!/bin/bash

# 钉钉机器人的webhook链接
webhook_url="https://oapi.dingtalk.com/robot/send?access_token=c52b63aebdb616e0b1e211025f90e6cca86eb8e1f019cec9863a222ee6bdedf9"

# 读取devices.txt文件中的每一行
while IFS= read -r line; do
  # 从当前行中提取"参数1"和"参数2"
  NAMESPACEID=$(echo "$line" | grep -oP '参数1:\K[^ ]+')
  GBID=$(echo "$line" | grep -oP '参数2:\K[^ ]+')

  # 执行python程序
  result=$(python check_online.py --NAMESPACEID "$NAMESPACEID" --GBID "$GBID")

  # 提取state字段信息
  state=$(echo "$result" | grep -oP 'state": "\K[^"]+')

  # 判断state字段信息并推送消息到钉钉机器人
  if [ "$state" == "online" ]; then
    curl -H 'Content-Type: application/json' -d '{"msgtype": "text","text": {"content":"[设备在线]"} }' "$webhook_url"
  elif [ "$state" == "online" ]; then
    curl -H 'Content-Type: application/json' -d '{"msgtype": "text","text": {"content":"[设备离线]"} }' "$webhook_url"
  fi
done < devices.txt