#!/bin/bash

# 钉钉机器人的webhook链接
webhook_url="https://oapi.dingtalk.com/robot/send?access_token=c52b63aebdb616e0b1e211025f90e6cca86eb8e1f019cec9863a222ee6bdedf9"

# 读取devices.txt文件中的每一行
while IFS=: read -r param1 param2 param3; do

  # 执行python程序
  result=$(python /home/check_online.py --NAMESPACEID "$(echo -e "$param1" )" --GBID "$(echo -e "$param2" )")
  echo $result
  # 检查python程序执行结果
  if [ $? -eq 0 ]; then
    # 提取state字段信息
    state=$(echo "$result" | jq -r '.state')

    # 根据state字段值推送消息给钉钉机器人
    if [ "$state" = "online" ]; then
      message="[${param3}设备在线]"
    else
      message="[${param3}设备离线]"
    fi
    curl -H 'Content-Type: application/json' -d '{"msgtype": "text","text": {"content":"'"$message"'"} }' "$webhook_url"
  else
    echo "Error: check_online.py execution failed"
  fi
done < devices.txt