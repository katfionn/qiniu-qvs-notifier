import requests

headers = {
    'authorization': 'Qiniu _cuhfevwcyWnDoIo6fRPXiI_Bs_vpCqv7EiGT1AH:2Uao8L3AlZ8dBbwhKCQmoFP49t4=',
}

response = requests.get('http://qvs.qiniuapi.com/v1/LiuMi-37XP5NQ08/devices', headers=headers)