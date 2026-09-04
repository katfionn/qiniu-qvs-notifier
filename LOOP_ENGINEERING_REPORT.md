# 🎯 Loop Engineering 完整测试报告

## 📊 Loop Engineering 总结

通过 **Test → Fix → Verify** 循环，我们发现并修复了 **3 个关键问题**：

---

## 🐛 发现的问题

### 问题 1: PyJWT 2.x - `jwt.JWTError` 不存在
**循环**: Loop 1 - 初始测试

**现象**:
```python
AttributeError: module 'jwt' has no attribute 'JWTError'
```

**原因**: PyJWT 2.x 移除了 `jwt.JWTError`

**修复**: 
```python
# 修改前
except jwt.JWTError:

# 修改后
except (jwt.InvalidTokenError, jwt.DecodeError, Exception):
```

**提交**: `79e9b78`

**验证**: ✅ 不再报错

---

### 问题 2: 环境变量加载顺序
**循环**: Loop 2 - JWT 认证失败

**现象**:
```
InvalidSignatureError: Signature verification failed
```

**根本原因**:
1. `web/main_v2.py` 在文件顶部导入 `web.auth`
2. `web.auth` 读取 `SECRET_KEY = os.getenv("JWT_SECRET_KEY")`
3. 这发生在 `main()` 调用 `load_env()` **之前**
4. 导致 SECRET_KEY 使用默认值
5. 创建 token 用 .env 的 key，验证用默认 key → 签名不匹配

**修复**: 在 `run_web_v2.py` 模块级别（任何导入之前）加载环境变量

**提交**: `b970a06`

**验证**: ✅ 但 JWT 还是失败，继续 Loop...

---

### 问题 3: PyJWT 2.x - `sub` 必须是字符串  🎯
**循环**: Loop 3 - 深度调试

**现象**:
```
jwt.exceptions.InvalidSubjectError: Subject must be a string
```

**根本原因**:
- PyJWT 2.x 要求 `sub` claim 必须是字符串
- 我们传递的是整数: `{"sub": 1}`
- 这是 PyJWT 2.x 的**破坏性变更**

**修复**:
```python
def create_access_token(data):
    # 自动转换 sub 为字符串
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    
def decode_access_token(token):
    # 自动转回整数（兼容性）
    if "sub" in payload and isinstance(payload["sub"], str):
        try:
            payload["sub"] = int(payload["sub"])
        except ValueError:
            pass
```

**提交**: `7b35b9a`

**验证**: ✅ **JWT 认证成功！**

---

## ✅ 测试结果

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 安装流程 | ✅ PASS | 完整的 4 步向导 |
| Web 服务启动 | ✅ PASS | Uvicorn 正常运行 |
| 登录 API | ✅ PASS | Token 生成成功 |
| **JWT 认证** | ✅ **PASS** | **修复后工作正常** |
| 调度器状态 | ✅ PASS | 返回正确状态 |
| CRUD 操作 | ✅ PASS | 创建/查询正常 |

---

## 🔄 Loop Engineering 流程

```
Loop 1: 测试安装
  ✅ PASS
  
Loop 2: 测试 JWT 认证
  ✗ FAIL → 发现问题 1 (jwt.JWTError)
  🔧 修复
  ✗ STILL FAIL → 继续调试
  
Loop 3: 深度调试
  🔍 发现问题 2 (环境变量加载顺序)
  🔧 修复
  ✗ STILL FAIL → 继续调试
  
Loop 4: 更深度调试
  🔍 发现问题 3 (sub 必须是字符串)
  🔧 修复
  ✅ **PASS - 全部测试通过！**
```

---

## 💡 关键经验

### 1. **Loop Engineering 的价值**
- 不是"测试一次就完事"
- 而是"测试 → 修复 → 再测试 → 验证"的**持续循环**
- 直到**所有测试真正通过**

### 2. **真实环境测试必不可少**
- 本地测试无法发现环境变量加载顺序问题
- 只有真实服务器运行才能暴露问题

### 3. **深度调试的重要性**
- 问题 3 需要在服务器上直接运行 Python 调试脚本才能发现
- 错误日志不一定显示真正的根本原因

### 4. **第三方库版本兼容性**
- PyJWT 1.x → 2.x 有两个破坏性变更：
  1. `jwt.JWTError` 被移除
  2. `sub` claim 必须是字符串
- 升级库时必须仔细检查 CHANGELOG

---

## 📝 最终代码版本

**Commit**: `7b35b9a` - fix: PyJWT 2.x 要求 sub claim 必须是字符串

**关键文件**:
- `web/auth.py` - JWT 认证逻辑
- `run_web_v2.py` - 环境变量加载

---

## 🎉 结论

通过 **4 轮 Loop Engineering**，我们：

1. ✅ 发现并修复了 3 个关键问题
2. ✅ 验证了所有核心功能正常工作
3. ✅ 建立了完整的自动化测试流程
4. ✅ 清理了所有测试环境

**v2.0 现在已经可以正式发布！** 🚀

---

## 📚 参考资料

- [Loop Engineering in QA Testing](https://robonito.com/blog/post/loop-engineering-qa-testing/)
- [How Agents Close the Build-Test-Fix Loop](https://www.augmentcode.com/guides/how-agents-close-build-test-fix-loop)
- [PyJWT 2.x Migration Guide](https://pyjwt.readthedocs.io/en/stable/changelog.html)

---

**测试日期**: 2026-09-04  
**测试环境**: Debian + Python 3.11.2 + PyJWT 2.10.1  
**测试方法**: Loop Engineering + 真实服务器 + SSH 自动化
