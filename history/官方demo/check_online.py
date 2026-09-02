# -*- coding: utf-8 -*-
from qiniu import QiniuMacAuth, http
import json


def listNamespacesInfo(access_key, secret_key, namespaceId, gbId):

    auth = QiniuMacAuth(access_key, secret_key)
    print(f'{auth}')
    print (auth)
    # 请求URL
    url = f"http://qvs.qiniuapi.com/v1/namespaces/{namespaceId}/devices/{gbId}"

    # 发起POST请求
    ret, res = http._get_with_qiniu_mac(url, params=None, auth=auth)
    headers = {"code": res.status_code, "reqid": res.req_id, "xlog": res.x_log, "text_body": res.text_body}

    # 格式化响应体
    Headers = json.dumps(headers, indent=4, ensure_ascii=False)
    result = json.dumps(ret, indent=4, ensure_ascii=False)
    return Headers, result


if __name__ == '__main__':
    # 七牛账号 AK、SK
    access_key = '{{access_key}}'
    secret_key = '{{secret_key}}'

    # 空间ID
    namespaceId = "NAMESPACEID"

    # 设备国标Id
    gbId = "GBID"

    headers, result = listNamespacesInfo(access_key, secret_key, namespaceId, gbId)
    print(f'{headers}\n{result}')