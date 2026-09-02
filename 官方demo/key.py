

import hmac
import base64
import hashlib



# -*- coding:utf-8 -*-

import hmac
import base64
import hashlib

data = "POST"+ " " + "/v1/namespaces/2xenzw32d1rf9/streams/31011500991180001471_34020000001320000001/domain" + \
"\nHost: " + "qvs.qiniuapi.com" + \
"\nContent-Type: " + "application/json" + "\n\n" + \
'{"domain":"qvs-live-hls.cpgroup.cn","domainType":"liveHls"}'
accessKey = '_cuhfevwcyWnDoIo6fRPXiI_Bs_vpCqv7EiGT1AH'
secretKey = 'LwXvSgvUbcP0A52iQ1BqaKTCQbds5IKIAqtfosVZ'
sign = hmac.new(secretKey, data, hashlib.sha1).digest()
encodedSign = base64.urlsafe_b64encode(sign)
authorization = 'Qiniu ' + accessKey + ':' + encodedSign
print(authorization)

#Qiniu _cuhfevwcyWnDoIo6fRPXiI_Bs_vpCqv7EiGT1AH:2Uao8L3AlZ8dBbwhKCQmoFP49t4=