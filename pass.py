#!/usr/bin/env python3
"""
Alfred 密码管理工具
功能：生成、保存、查询、管理密码
"""

import sys
import sqlite3
import random
import string
import os
import time
import json

# 尝试导入 pyperclip，如果失败则使用备用方案
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    # 不在 Alfred 中输出警告到 stderr，避免干扰
    pass

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "passwords.db")

# ============================================================================
# 工具函数
# ============================================================================

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

def alfred_output(items):
    """输出 Alfred 标准格式的 JSON"""
    output = {"items": []}
    for item in items:
        if isinstance(item, tuple):
            name, subtitle = item
            alfred_item = {
                "title": name or "",
                "subtitle": subtitle or "",
                "arg": name or "",
                "autocomplete": name or "",
                "valid": True
            }
        else:
            name = item.get("title", "")
            subtitle = item.get("subtitle", "")
            
            # 构建 Alfred 标准格式
            alfred_item = {
                "title": name or "",
                "subtitle": subtitle or "",
                "arg": item.get("arg", name) or "",
                "autocomplete": item.get("autocomplete", name) or "",
                "valid": item.get("valid", True)
            }
        
        output["items"].append(alfred_item)
    
    # 确保输出到 stdout，使用 json.dumps 格式化输出
    # 不输出到 stderr，避免干扰 Alfred
    try:
        json_output = json.dumps(output, ensure_ascii=False)
        print(json_output, flush=True)
    except Exception as e:
        # 如果 JSON 序列化失败，输出错误信息
        error_output = {
            "items": [{
                "title": "错误",
                "subtitle": f"输出格式错误: {str(e)}",
                "valid": False
            }]
        }
        print(json.dumps(error_output, ensure_ascii=False), flush=True)

# ============================================================================
# 数据库操作
# ============================================================================

def init_db():
    """初始化数据库"""
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

def save_password(name, password):
    """保存密码"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO passwords (name, password, created_at) VALUES (?, ?, ?)",
        (name, password, int(time.time()))
    )
    conn.commit()
    conn.close()

def get_password(name):
    """获取密码"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password FROM passwords WHERE name=?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def list_passwords():
    """列出所有密码名称"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM passwords ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [name for (name,) in rows]

def delete_password(name):
    """删除密码"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM passwords WHERE name=?", (name,))
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    return deleted_count > 0

def clear_all_passwords():
    """清空所有密码"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 先获取删除前的数量
    c.execute("SELECT COUNT(*) FROM passwords")
    count_before = c.fetchone()[0]
    # 执行删除
    c.execute("DELETE FROM passwords")
    conn.commit()
    conn.close()
    return count_before

# ============================================================================
# 密码生成
# ============================================================================

def generate_password(length=16):
    """生成随机密码"""
    chars = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return ''.join(random.choice(chars) for _ in range(length))

# ============================================================================
# 命令处理函数
# ============================================================================

def handle_list_command():
    """处理列表命令"""
    rows = list_passwords()
    if rows:
        items = []
        for name in rows:
            pwd = get_password(name)
            if pwd:
                items.append({
                    "title": name,
                    "subtitle": f"点击复制密码: {pwd[:20]}..." if len(pwd) > 20 else f"点击复制密码: {pwd}",
                    "arg": pwd,  # 直接传递密码，让 Alfred 复制
                    "autocomplete": name
                })
            else:
                items.append({
                    "title": name,
                    "subtitle": "密码不存在",
                    "arg": "",
                    "valid": False,
                    "autocomplete": name
                })
        alfred_output(items)
    else:
        alfred_output([("无密码记录", "使用 'pwd 长度 标签' 生成密码")])

def handle_clear_command(query):
    """处理清空命令"""
    if query.strip().lower() == "clear":
        # 获取当前密码数量
        current_count = len(list_passwords())
        if current_count > 0:
            alfred_output([("⚠️ 确认清空", f"输入 'clear confirm' 来确认清空所有密码（当前有 {current_count} 个密码）")])
        else:
            alfred_output([("⚠️ 确认清空", "输入 'clear confirm' 来确认清空所有密码（当前没有密码）")])
    elif query.strip().lower() == "clear confirm":
        count = clear_all_passwords()
        if count > 0:
            # 清空后，验证是否真的清空了
            remaining = len(list_passwords())
            if remaining == 0:
                alfred_output([("✅ 清空完成", f"已成功删除 {count} 个密码记录")])
            else:
                alfred_output([("⚠️ 清空部分完成", f"已删除 {count} 个密码记录，但仍有 {remaining} 个密码未删除")])
        else:
            alfred_output([("清空完成", "没有密码记录需要删除")])
    else:
        current_count = len(list_passwords())
        if current_count > 0:
            alfred_output([("⚠️ 确认清空", f"输入 'clear confirm' 来确认清空所有密码（当前有 {current_count} 个密码）")])
        else:
            alfred_output([("⚠️ 确认清空", "输入 'clear confirm' 来确认清空所有密码（当前没有密码）")])

def handle_delete_command(query_args):
    """处理删除命令"""
    if len(query_args) == 1:
        alfred_output([{"title": "删除密码", "subtitle": "用法: del 密码名称", "valid": False}])
    elif len(query_args) == 2:
        name = query_args[1]
        # 直接删除，不需要确认步骤
        if delete_password(name):
            alfred_output([{"title": "✅ 删除成功", "subtitle": f"已删除密码: {name}", "arg": "", "valid": False}])
        else:
            alfred_output([{"title": "删除失败", "subtitle": f"未找到密码: {name}", "arg": "", "valid": False}])
    else:
        # 如果参数超过2个，尝试删除第一个参数作为密码名称
        name = query_args[1]
        if delete_password(name):
            alfred_output([{"title": "✅ 删除成功", "subtitle": f"已删除密码: {name}", "arg": "", "valid": False}])
        else:
            alfred_output([{"title": "删除失败", "subtitle": f"未找到密码: {name}", "arg": "", "valid": False}])

def handle_regen_command(query_args):
    """处理重新生成命令"""
    if len(query_args) >= 2:
        # 检查最后一个参数是否是数字（长度参数）
        # 如果是数字，则从第二个参数到倒数第二个参数是标签名，最后一个是长度
        # 如果不是数字，则从第二个参数开始的所有参数都是标签名
        if len(query_args) >= 3 and query_args[-1].isdigit():
            # 最后一个参数是长度
            name = ' '.join(query_args[1:-1])  # 从第二个到倒数第二个
            length = int(query_args[-1])
        else:
            # 合并所有后面的参数作为标签名，支持多词标签
            name = ' '.join(query_args[1:])
            length = 16
        pwd = generate_password(length)
        save_password(name, pwd)
        # 在 Alfred 中，让 Alfred 负责复制，arg 字段包含密码即可
        alfred_output([{"title": name, "subtitle": f"已重新生成，点击复制: {pwd}", "arg": pwd}])

def handle_generate_password(query_args):
    """处理生成密码命令"""
    length = int(query_args[0])
    # 合并所有后面的参数作为标签名，支持多词标签（如 "crm 测试服务器"）
    name = ' '.join(query_args[1:]) if len(query_args) > 1 else f"pwd_{int(time.time())}"
    pwd = generate_password(length)
    save_password(name, pwd)
    # 在 Alfred 中，让 Alfred 负责复制，arg 字段包含密码即可
    alfred_output([{"title": name, "subtitle": f"已生成并保存，点击复制: {pwd}", "arg": pwd}])

def handle_save_password(query_args):
    """处理保存密码命令"""
    name = query_args[0]
    pwd = ' '.join(query_args[1:])
    save_password(name, pwd)
    # 在 Alfred 中，让 Alfred 负责复制，arg 字段包含密码即可
    alfred_output([{"title": name, "subtitle": f"已保存，点击复制: {pwd}", "arg": pwd}])

def handle_query_password(query_args):
    """处理查询密码命令"""
    name = query_args[0]
    pwd = get_password(name)
    if pwd:
        # 在 Alfred 中，让 Alfred 负责复制，arg 字段包含密码即可
        alfred_output([{"title": name, "subtitle": f"点击复制密码: {pwd}", "arg": pwd}])
    else:
        alfred_output([("未找到密码", "可用 '标签 密码' 保存新密码或 '长度 标签' 生成密码")])

def handle_smart_search(query):
    """处理智能搜索"""
    all_passwords = list_passwords()
    
    # 先检查是否有完全匹配的密码名称
    exact_match = None
    for name in all_passwords:
        if name.lower() == query.lower():
            exact_match = name
            break
    
    if exact_match:
        # 完全匹配，直接查询密码
        pwd = get_password(exact_match)
        if pwd:
            # 在 Alfred 中，让 Alfred 负责复制，arg 字段包含密码即可
            alfred_output([{"title": exact_match, "subtitle": f"点击复制密码: {pwd}", "arg": pwd}])
        else:
            alfred_output([("未找到密码", "可用 '标签 密码' 保存新密码或 '长度 标签' 生成密码")])
        return
    
    # 没有完全匹配，进行模糊搜索
    matching_passwords = [name for name in all_passwords if query.lower() in name.lower()]
    
    if matching_passwords:
        items = []
        for name in matching_passwords:
            pwd = get_password(name)
            if pwd:
                items.append({
                    "title": name,
                    "subtitle": f"点击复制密码: {pwd[:20]}..." if len(pwd) > 20 else f"点击复制密码: {pwd}",
                    "arg": pwd,  # 直接传递密码，让 Alfred 复制
                    "autocomplete": name
                })
            else:
                items.append({
                    "title": name,
                    "subtitle": "密码不存在",
                    "arg": "",
                    "valid": False,
                    "autocomplete": name
                })
        alfred_output(items)
    else:
        alfred_output([("未找到密码", "可用 '标签 密码' 保存新密码或 '长度 标签' 生成密码")])

def show_help():
    """显示帮助信息"""
    # 获取当前密码数量
    password_count = len(list_passwords())
    
    help_items = [
        {
            "title": "🔐 密码管理工具",
            "subtitle": f"当前已保存 {password_count} 个密码",
            "arg": "",
            "valid": False
        },
        {
            "title": "生成密码",
            "subtitle": "pwd 16 github - 生成16位密码并保存为github",
            "arg": "",
            "autocomplete": "16 ",
            "valid": False  # 帮助项不应该执行动作，只用于提示
        },
        {
            "title": "保存密码", 
            "subtitle": "pwd github mypass - 保存密码为github",
            "arg": "",
            "autocomplete": "github ",
            "valid": False
        },
        {
            "title": "查询密码",
            "subtitle": "pwd github - 查询并复制github密码",
            "arg": "",
            "autocomplete": "github",
            "valid": False
        },
        {
            "title": "列出密码",
            "subtitle": "pwd list - 显示所有保存的密码",
            "arg": "",
            "autocomplete": "list",
            "valid": False
        },
        {
            "title": "删除密码",
            "subtitle": "pwd del github confirm - 删除github密码",
            "arg": "",
            "autocomplete": "del ",
            "valid": False
        },
        {
            "title": "清空密码",
            "subtitle": "pwd clear confirm - 清空所有密码",
            "arg": "",
            "autocomplete": "clear confirm",
            "valid": False
        },
        {
            "title": "重新生成",
            "subtitle": "pwd regen github - 为github重新生成密码",
            "arg": "",
            "autocomplete": "regen ",
            "valid": False
        }
    ]
    
    # 如果有密码，添加快速访问选项
    if password_count > 0:
        all_passwords = list_passwords()
        help_items.append({
            "title": "📋 快速访问",
            "subtitle": "点击查看所有保存的密码",
            "arg": "",
            "autocomplete": "list",
            "valid": False
        })
        
        # 显示最近的几个密码 - 直接返回密码值
        recent_passwords = all_passwords[:3]  # 显示最近3个
        for name in recent_passwords:
            pwd = get_password(name)
            if pwd:
                help_items.append({
                    "title": f"🔑 {name}",
                    "subtitle": f"点击复制密码: {pwd[:20]}..." if len(pwd) > 20 else f"点击复制密码: {pwd}",
                    "arg": pwd,  # 直接返回密码值，而不是名称
                    "autocomplete": name
                })
            else:
                help_items.append({
                    "title": f"🔑 {name}",
                    "subtitle": "密码不存在",
                    "arg": "",
                    "valid": False,
                    "autocomplete": name
                })
    
    alfred_output(help_items)

# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""
    # 初始化数据库
    try:
        init_db()
    except Exception as e:
        alfred_output([("数据库错误", f"无法初始化数据库: {str(e)}")])
        return
    
    # 获取命令行参数
    # Alfred 可能传递空字符串、None 或特殊值
    try:
        args = sys.argv[1:]
        if len(args) > 0 and args[0]:
            # 处理 Alfred 可能传递的特殊值
            query = args[0].strip() if args[0] not in ["(null)", "null", ""] else ""
        else:
            query = ""
    except (IndexError, AttributeError):
        query = ""
    
    # 将查询分割为参数数组
    query_args = query.split() if query else []
    
    # 处理空查询
    if not query or (isinstance(query, str) and query.isspace()):
        show_help()
        return
    
    # 处理系统消息（删除成功、清空完成等），直接显示帮助，避免被重新处理
    system_messages = ["✅ 删除成功", "删除成功", "删除失败", "✅ 清空完成", "清空完成", "清空失败"]
    if query.strip() in system_messages or query.strip().startswith("✅") or query.strip().startswith("❌"):
        show_help()
        return
    
    # 处理输入长度检查
    if len(query) < 2:
        alfred_output([{"title": "输入中...", "subtitle": "继续输入以搜索或生成密码", "valid": False}])
        return
    
    # 防止输入过程中的中间状态被当作密码保存
    # 如果只有数字参数（如 "16 "），应该等待输入标签名
    if (len(query_args) == 1 and 
        query_args[0].isdigit()):
        alfred_output([{"title": "输入中...", "subtitle": f"继续输入标签名（当前长度: {query_args[0]}）", "valid": False}])
        return
    
    # 只对非常短的标签名（1-2个字符）进行保护，3个字符及以上允许立即生成
    if (len(query_args) == 2 and 
        query_args[0].isdigit() and 
        len(query_args[1]) <= 2):
        alfred_output([{"title": "输入中...", "subtitle": f"继续输入标签名，当前: {query_args[1]}", "valid": False}])
        return
    
    # 额外保护：如果标签名看起来像是不完整的输入（仅两个参数时）
    # 只检查明显不完整的模式（1-2个字符的常见前缀）
    if (len(query_args) == 2 and 
        query_args[0].isdigit() and 
        query_args[1].lower() in ['gi', 'g']):
        alfred_output([{"title": "输入中...", "subtitle": f"继续输入完整标签名，当前: {query_args[1]}", "valid": False}])
        return
    
    # 检查特殊命令
    is_special_command = any(cmd in [arg.lower() for arg in query_args] for cmd in ['list', 'clear', 'del', 'regen'])
    is_number_start = query_args[0].isdigit() if query_args and len(query_args) > 0 else False
    
    # 处理特殊命令
    # 支持前缀匹配，如 "lis"、"li" 可以匹配 "list"
    if query_args and len(query_args) > 0:
        first_arg = query_args[0].lower()
        # 检查是否是 list 命令（完全匹配或前缀匹配）
        if first_arg == "list" or (len(first_arg) >= 2 and first_arg in ["li", "lis"]):
            handle_list_command()
            return
        
        if first_arg == "del":
            handle_delete_command(query_args)
            return
        
        # 检查是否是 regen 命令（完全匹配或前缀匹配）
        if first_arg == "regen" or (len(first_arg) >= 3 and first_arg in ["reg", "rege"]):
            handle_regen_command(query_args)
            return
    
    if query_args and "clear" in [arg.lower() for arg in query_args]:
        handle_clear_command(query)
        return
    
    # 处理生成密码（数字开头）
    if is_number_start:
        handle_generate_password(query_args)
        return
    
    # 处理保存密码（非数字开头，多个参数）
    # 但排除包含 emoji 或特殊字符的情况（可能是帮助项或系统消息）
    if (len(query_args) >= 2 and not is_number_start and 
        not any(char in query for char in ['🔐', '🔑', '📋', '⚠️', '✅', '❌'])):
        handle_save_password(query_args)
        return
    
    # 智能搜索（单个参数，非特殊命令，非数字开头）
    if not is_special_command and not is_number_start and len(query_args) == 1:
        # 如果包含 emoji，可能是帮助项，直接显示帮助
        if any(char in query for char in ['🔐', '🔑', '📋', '⚠️']):
            show_help()
            return
        handle_smart_search(query)
        return
    
    # 默认查询密码
    if query_args and len(query_args) > 0:
        # 如果包含 emoji，可能是帮助项或系统消息，直接显示帮助
        if any(char in query for char in ['🔐', '🔑', '📋', '⚠️', '✅', '❌']):
            show_help()
            return
        handle_query_password(query_args)
    else:
        show_help()

if __name__ == "__main__":
    main()