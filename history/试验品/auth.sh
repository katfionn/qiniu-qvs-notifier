#!/bin/bash

# 这里是HMAC、Base64和Hashlib的Bash版本
# HMAC
hmac_sha1() {
  key=$1
  data=$2
  echo -n "$data" | openssl dgst -sha1 -hmac "$key" -binary | base64 | tr -d '='
}

# Base64
base64_urlsafe() {
  echo -n "$1" | openssl enc -base64 | tr '/+' '_-'
}

# Hashlib (这里我们用sha1，和python的hashlib.sha1一样)
sha1() {
  echo -n "$1" | openssl dgst -sha1 -binary | base64 | tr -d '='
}

# 拼接规则
data='POST /v1/namespaces/2xenzw32d1rf9/streams/31011500991180001471_34020000001320000001/domain'
data+="Host: qvs.qiniuapi.com\nContent-Type: application/json\n\n"
json_data='{"domain":"qvs-live-hls.cpgroup.cn","domainType":"liveHls"}'
data+="$json_data"

# accessKey和secretKey需要你自己替换
accessKey='_cuhfevwcyWnDoIo6fRPXiI_Bs_vpCqv7EiGT1AH'
secretKey='LwXvSgvUbcP0A52iQ1BqaKTCQbds5IKIAqtfosVZ'

# 计算签名
sign=$(hmac_sha1 "$secretKey" "$data" | base64_urlsafe)

# 创建授权字符串
auth="Qiniu $accessKey:$sign"

# 打印授权字符串
echo "$auth"

# 读取devices.txt文件中的参数，并逐行执行脚本
while IFS=":" read -r param1 param2 param3; do

  # 发送HTTP请求并获取返回
  result=$(curl -s -X GET "https://qvs.qiniuapi.com/v1/namespaces/$param1/devices/$param2" -H "Authorization: $auth")
  echo $result
  # 提取返回中的"state"参数的值
  state=$(echo "$result" | grep -oP '(?<="state":")\K[^"]+')

  # 根据状态向钉钉机器人发送webhook消息
  if [ "$state" == "online" ]; then
    message="[$param3设备在线]"
  else
    message="[$param3设备离线]"
  fi

  # 使用curl发送webhook消息给钉钉机器人
  curl -X POST -H "Content-Type: application/json" -d '{"msgtype": "text", "text": {"content": "'$message'"}}' "https://oapi.dingtalk.com/robot/send?access_token=c52b63aebdb616e0b1e211025f90e6cca86eb8e1f019cec9863a222ee6bdedf9"
done < "devices.txt"