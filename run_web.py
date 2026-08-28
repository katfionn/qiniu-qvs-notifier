import uvicorn
import sys

if __name__ == "__main__":
    print("启动系统配置中心...")
    print("请在浏览器中访问: http://127.0.0.1:8000")
    # 也可以读取刚刚 install.py 生成的 settings.yaml，如果有绑定限制等
    uvicorn.run("web.main:app", host="0.0.0.0", port=8000, reload=True)
