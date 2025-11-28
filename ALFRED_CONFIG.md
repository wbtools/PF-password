# Alfred Workflow 配置指南

## 配置步骤

### 1. Script Filter 节点配置

#### 基本设置
- **Keyword**: `pwd`
- **with space**: ✅ 勾选（这样输入 `pwd ` 才会触发）
- **Argument Optional**: 选择 "Argument Optional" 或 "Argument Required"

#### Script 配置（推荐方式一：使用 Python 直接运行）

**Language**: 选择 `/usr/bin/python3` 或直接使用 Python 解释器路径

**Script**:
```python
import sys
import json
import os

# 获取 Alfred 传入的查询参数
query = sys.argv[1] if len(sys.argv) > 1 else ""

# 执行主脚本
script_path = "/Users/pfinal/python/PF-password/pass.py"
os.system(f'/Users/pfinal/.pyenv/versions/base3.12/bin/python "{script_path}" "{query}"')
```

#### Script 配置（推荐方式二：使用 Shell）

**Language**: `/bin/zsh`

**Script**:
```bash
/Users/pfinal/.pyenv/versions/base3.12/bin/python /Users/pfinal/python/PF-password/pass.py "$1"
```

**重要**：确保 `"$1"` 有引号，这样可以正确处理包含空格的参数。

#### Script 配置（推荐方式三：使用完整路径和错误处理）

**Language**: `/bin/zsh`

**Script**:
```bash
cd /Users/pfinal/python/PF-password
/Users/pfinal/.pyenv/versions/base3.12/bin/python pass.py "$1" 2>/dev/null
```

### 2. 后续节点配置

#### Copy to Clipboard 节点
- **Type**: Plain Text
- **Text**: `{query}` （这会复制选中项的 `arg` 值）
- **Automatically paste to frontmost app**: ✅ 可选，勾选后会自动粘贴

#### Run Script 节点（如果需要）
- 通常不需要，因为密码已经通过 `arg` 字段传递

### 3. 常见问题排查

#### 问题 1: 脚本没有输出
- 检查 Python 路径是否正确
- 检查脚本文件是否有执行权限
- 在终端手动运行脚本测试：`/Users/pfinal/.pyenv/versions/base3.12/bin/python /Users/pfinal/python/PF-password/pass.py "test"`

#### 问题 2: 参数传递不正确
- 确保使用 `"$1"` 而不是 `$1`（带引号）
- 检查 Script Filter 的 "with input as argv" 选项已选中

#### 问题 3: JSON 格式错误
- 确保脚本输出的是有效的 JSON
- 检查是否有错误信息输出到 stderr（应该被重定向）

### 4. 测试命令

在终端中测试脚本是否正常工作：
```bash
cd /Users/pfinal/python/PF-password
/Users/pfinal/.pyenv/versions/base3.12/bin/python pass.py ""
/Users/pfinal/python/PF-password/pass.py "list"
/Users/pfinal/python/PF-password/pass.py "github"
```

输出应该是有效的 JSON 格式。

