#!/usr/bin/env python3
import sys, sqlite3, random, string, os, time, json

# 尝试导入 pyperclip，如果失败则使用备用方案
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    print("警告: pyperclip 未安装，将使用备用复制方案", file=sys.stderr)

DB_PATH = os.path.join(os.path.dirname(__file__), "passwords.db")

def safe_copy_to_clipboard(text):
    """安全地复制文本到剪贴板，包含错误处理"""
    try:
        if CLIPBOARD_AVAILABLE:
            pyperclip.copy(text)
            return True
        else:
            # 备用方案：使用 macOS 的 pbcopy 命令
            import subprocess
            result = subprocess.run(['pbcopy'], input=text, text=True, capture_output=True)
            if result.returncode == 0:
                return True
            else:
                print(f"pbcopy 失败: {result.stderr.decode()}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"复制失败: {e}", file=sys.stderr)
        # 最后的备用方案：直接输出到 stderr，用户可以手动复制
        print(f"请手动复制: {text}", file=sys.stderr)
        return False

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            password TEXT,
            created_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def generate_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return ''.join(random.choice(chars) for _ in range(length))

def save_password(name, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO passwords (name, password, created_at) VALUES (?, ?, ?)",
        (name, password, int(time.time()))
    )
    conn.commit()
    conn.close()

def get_password(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password FROM passwords WHERE name=?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def list_passwords():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM passwords ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [name for (name,) in rows]

def delete_password(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM passwords WHERE name=?", (name,))
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    return deleted_count > 0

def clear_all_passwords():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM passwords")
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def alfred_output(items):
    output = {"items": []}
    for item in items:
        if isinstance(item, tuple):
            name, subtitle = item
        else:
            name, subtitle = item.get("title"), item.get("subtitle")
        
        # 构建 Alfred 标准格式
        alfred_item = {
            "title": name,
            "subtitle": subtitle,
            "arg": name,
            "autocomplete": name,
            "valid": True
        }
        
        # 如果是字典格式，保留其他字段
        if isinstance(item, dict):
            if "arg" in item:
                alfred_item["arg"] = item["arg"]
            if "valid" in item:
                alfred_item["valid"] = item["valid"]
        
        output["items"].append(alfred_item)
    
    # 确保输出到 stdout，使用 json.dumps 格式化输出
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    init_db()
    args = sys.argv[1:]
    query = ' '.join(args).strip()

    # 处理 Alfred 可能传递的空参数或只包含空格的情况
    if not query or query.isspace():
        alfred_output([("提示", "生成: pwd 16 标签 / 保存: pwd 标签 密码 / 查询: pwd 标签 / 列表: pwd list / 删除: pwd del 标签 / 清空: pwd clear")])
        sys.exit(0)

    query_args = query.split()

    # 如果第一个参数是空字符串或只包含空格，显示帮助
    if not query_args or not query_args[0]:
        alfred_output([("提示", "生成: pwd 16 标签 / 保存: pwd 标签 密码 / 查询: pwd 标签 / 列表: pwd list / 删除: pwd del 标签 / 清空: pwd clear")])
        sys.exit(0)

    # 列出所有标签（安全模式，不显示密码）
    if "list" in [arg.lower() for arg in query_args]:
        rows = list_passwords()
        if rows:
            items = []
            for name in rows:
                items.append({
                    "title": name,
                    "subtitle": "点击生成新密码并复制",
                    "arg": f"regen {name}",
                    "autocomplete": name
                })
            alfred_output(items)
        else:
            alfred_output([("无密码记录", "使用 'pwd 长度 标签' 生成密码")])
        sys.exit(0)

    # 清空所有密码
    if "clear" in [arg.lower() for arg in query_args]:
        count = clear_all_passwords()
        if count > 0:
            alfred_output([("清空完成", f"已删除 {count} 个密码记录")])
        else:
            alfred_output([("清空完成", "没有密码记录需要删除")])
        sys.exit(0)

    # 删除指定密码
    if query_args[0].lower() == "del" and len(query_args) >= 2:
        name = query_args[1]
        if delete_password(name):
            alfred_output([("删除成功", f"已删除密码: {name}")])
        else:
            alfred_output([("删除失败", f"未找到密码: {name}")])
        sys.exit(0)

    # 点击标签生成新密码
    if query_args[0].lower() == "regen" and len(query_args) >= 2:
        name = query_args[1]
        length = int(query_args[2]) if len(query_args) >= 3 and query_args[2].isdigit() else 16
        pwd = generate_password(length)
        save_password(name, pwd)
        copy_success = safe_copy_to_clipboard(pwd)
        status = "已生成新密码并复制" if copy_success else "已生成新密码（复制失败，请手动复制）"
        alfred_output([{"title": name, "subtitle": f"{pwd}（{status}）", "arg": pwd}])
        sys.exit(0)

    # 生成密码
    if query_args[0].isdigit():
        length = int(query_args[0])
        name = query_args[1] if len(query_args) > 1 else f"pwd_{int(time.time())}"
        pwd = generate_password(length)
        save_password(name, pwd)
        copy_success = safe_copy_to_clipboard(pwd)
        status = "已保存并复制" if copy_success else "已保存（复制失败，请手动复制）"
        alfred_output([{"title": name, "subtitle": f"{pwd}（{status}）", "arg": pwd}])
        sys.exit(0)

    # 保存已有密码
    if len(query_args) >= 2:
        name = query_args[0]
        pwd = ' '.join(query_args[1:])
        save_password(name, pwd)
        copy_success = safe_copy_to_clipboard(pwd)
        status = "已保存并复制" if copy_success else "已保存（复制失败，请手动复制）"
        alfred_output([{"title": name, "subtitle": f"{pwd}（{status}）", "arg": pwd}])
        sys.exit(0)

    # 查询密码
    
    name = query_args[0]
    pwd = get_password(name)
    if pwd:
        copy_success = safe_copy_to_clipboard(pwd)
        status = "已复制" if copy_success else "复制失败，请手动复制"
        # 将 arg 设置为实际密码，这样 Alfred 的 Copy to Clipboard 会复制密码而不是标签名
        alfred_output([{"title": name, "subtitle": f"{pwd}（{status}）", "arg": pwd}])
    else:
        alfred_output([("未找到密码", "可用 '标签 密码' 保存新密码或 '长度 标签' 生成密码")])
