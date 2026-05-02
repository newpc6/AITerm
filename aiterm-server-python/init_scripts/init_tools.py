"""
工具初始化脚本
运行此脚本可以导入预设的工具到数据库中

使用方法:
    cd aiterm-server-python
    python scripts/init_tools.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import async_session_maker, engine
from app.db.tool import ToolModel
from app.db.base import Base
from sqlalchemy import select


DEFAULT_TOOLS = [
    {
        "name": "get_current_time",
        "display_name": "获取当前时间",
        "description": "获取当前的日期、时间和星期。当用户询问现在几点、今天日期、当前时间等问题时，必须调用此工具获取准确的实时时间。模型本身无法获取实时时间，必须通过此工具才能获得准确的时间信息。",
        "code": '''def execute(arguments):
    """
    获取当前日期和时间
    """
    from datetime import datetime
    now = datetime.now()
    return {
        "success": True,
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    }
''',
        "enabled": True
    },
    {
        "name": "calculate",
        "display_name": "数学计算",
        "description": "执行数学表达式计算，支持基本运算和常用数学函数",
        "code": '''def execute(arguments):
    """
    执行数学计算
    arguments:
        expression: 数学表达式，如 "2 + 3 * 4"
    """
    import math
    expression = arguments.get("expression", "")
    if not expression:
        return {"success": False, "error": "请提供数学表达式"}
    
    allowed_names = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow, "sqrt": math.sqrt,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "pi": math.pi, "e": math.e
    }
    
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"success": True, "expression": expression, "result": result}
    except Exception as e:
        return {"success": False, "error": f"计算错误: {str(e)}"}
''',
        "enabled": True
    },
    {
        "name": "generate_uuid",
        "display_name": "生成UUID",
        "description": "生成UUID通用唯一识别码",
        "code": '''def execute(arguments):
    """
    生成UUID
    arguments:
        count: 生成数量，默认1个
    """
    import uuid
    count = arguments.get("count", 1)
    if count < 1:
        count = 1
    if count > 100:
        count = 100
    
    uuids = [str(uuid.uuid4()) for _ in range(count)]
    return {
        "success": True,
        "count": len(uuids),
        "uuids": uuids
    }
''',
        "enabled": True
    },
    {
        "name": "encode_decode",
        "display_name": "编解码转换",
        "description": "字符串编解码转换，支持base64、url、html等",
        "code": '''def execute(arguments):
    """
    编解码转换
    arguments:
        text: 要转换的文本
        operation: 操作类型 (base64_encode, base64_decode, url_encode, url_decode, html_escape, html_unescape)
    """
    import base64
    import urllib.parse
    import html
    
    text = arguments.get("text", "")
    operation = arguments.get("operation", "base64_encode")
    
    try:
        if operation == "base64_encode":
            result = base64.b64encode(text.encode()).decode()
        elif operation == "base64_decode":
            result = base64.b64decode(text.encode()).decode()
        elif operation == "url_encode":
            result = urllib.parse.quote(text)
        elif operation == "url_decode":
            result = urllib.parse.unquote(text)
        elif operation == "html_escape":
            result = html.escape(text)
        elif operation == "html_unescape":
            result = html.unescape(text)
        else:
            return {"success": False, "error": f"未知操作: {operation}"}
        
        return {"success": True, "operation": operation, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
''',
        "enabled": True
    },
    {
        "name": "json_format",
        "display_name": "JSON格式化",
        "description": "JSON字符串格式化和验证",
        "code": '''def execute(arguments):
    """
    JSON格式化
    arguments:
        json_string: JSON字符串
        indent: 缩进空格数，默认2
    """
    import json
    
    json_string = arguments.get("json_string", "")
    indent = arguments.get("indent", 2)
    
    try:
        parsed = json.loads(json_string)
        formatted = json.dumps(parsed, indent=indent, ensure_ascii=False)
        return {
            "success": True,
            "formatted": formatted,
            "type": type(parsed).__name__,
            "size": len(parsed) if isinstance(parsed, (list, dict)) else None
        }
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON解析错误: {str(e)}"}
''',
        "enabled": True
    },
    {
        "name": "generate_password",
        "display_name": "生成密码",
        "description": "生成随机密码，可指定长度和字符类型",
        "code": '''def execute(arguments):
    """
    生成随机密码
    arguments:
        length: 密码长度，默认16
        include_uppercase: 包含大写字母，默认True
        include_lowercase: 包含小写字母，默认True
        include_digits: 包含数字，默认True
        include_symbols: 包含特殊符号，默认False
    """
    import random
    import string
    
    length = arguments.get("length", 16)
    if length < 4:
        length = 4
    if length > 128:
        length = 128
    
    chars = ""
    if arguments.get("include_lowercase", True):
        chars += string.ascii_lowercase
    if arguments.get("include_uppercase", True):
        chars += string.ascii_uppercase
    if arguments.get("include_digits", True):
        chars += string.digits
    if arguments.get("include_symbols", False):
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    if not chars:
        chars = string.ascii_letters + string.digits
    
    password = "".join(random.choice(chars) for _ in range(length))
    return {
        "success": True,
        "password": password,
        "length": length
    }
''',
        "enabled": True
    },
    {
        "name": "text_statistics",
        "display_name": "文本统计",
        "description": "统计文本的字符数、单词数、行数等信息",
        "code": '''def execute(arguments):
    """
    文本统计
    arguments:
        text: 要统计的文本
    """
    import re
    
    text = arguments.get("text", "")
    
    lines = text.split("\\n") if text else []
    words = re.findall(r"\\b\\w+\\b", text)
    
    char_count = len(text)
    char_count_no_space = len(text.replace(" ", "").replace("\\n", "").replace("\\t", ""))
    word_count = len(words)
    line_count = len(lines)
    
    chinese_chars = len(re.findall(r"[\\u4e00-\\u9fff]", text))
    english_chars = len(re.findall(r"[a-zA-Z]", text))
    digits = len(re.findall(r"\\d", text))
    
    return {
        "success": True,
        "statistics": {
            "characters": char_count,
            "characters_no_space": char_count_no_space,
            "words": word_count,
            "lines": line_count,
            "chinese_characters": chinese_chars,
            "english_characters": english_chars,
            "digits": digits
        }
    }
''',
        "enabled": True
    },
    {
        "name": "color_converter",
        "display_name": "颜色转换",
        "description": "颜色格式转换，支持HEX、RGB、HSL等格式",
        "code": '''def execute(arguments):
    """
    颜色格式转换
    arguments:
        color: 颜色值
        from_format: 源格式 (hex, rgb, hsl)
        to_format: 目标格式 (hex, rgb, hsl)
    """
    import re
    
    color = arguments.get("color", "")
    from_format = arguments.get("from_format", "hex")
    to_format = arguments.get("to_format", "rgb")
    
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_hex(r, g, b):
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def rgb_to_hsl(r, g, b):
        r, g, b = r/255, g/255, b/255
        max_c, min_c = max(r, g, b), min(r, g, b)
        l = (max_c + min_c) / 2
        if max_c == min_c:
            h = s = 0
        else:
            d = max_c - min_c
            s = d / (2 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)
            if max_c == r:
                h = (g - b) / d + (6 if g < b else 0)
            elif max_c == g:
                h = (b - r) / d + 2
            else:
                h = (r - g) / d + 4
            h /= 6
        return round(h * 360), round(s * 100), round(l * 100)
    
    try:
        if from_format == "hex":
            r, g, b = hex_to_rgb(color)
        elif from_format == "rgb":
            match = re.match(r"rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)", color)
            if not match:
                return {"success": False, "error": "无效的RGB格式"}
            r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        else:
            return {"success": False, "error": f"不支持的源格式: {from_format}"}
        
        if to_format == "hex":
            result = rgb_to_hex(r, g, b)
        elif to_format == "rgb":
            result = f"rgb({r}, {g}, {b})"
        elif to_format == "hsl":
            h, s, l = rgb_to_hsl(r, g, b)
            result = f"hsl({h}, {s}%, {l}%)"
        else:
            return {"success": False, "error": f"不支持的目标格式: {to_format}"}
        
        return {"success": True, "original": color, "converted": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
''',
        "enabled": True
    },
    {
        "name": "regex_match",
        "display_name": "正则匹配",
        "description": "使用正则表达式匹配文本",
        "code": '''def execute(arguments):
    """
    正则表达式匹配
    arguments:
        pattern: 正则表达式
        text: 要匹配的文本
        flags: 可选标志 (ignore_case, multiline, dotall)
    """
    import re
    
    pattern = arguments.get("pattern", "")
    text = arguments.get("text", "")
    flags = arguments.get("flags", [])
    
    re_flags = 0
    if "ignore_case" in flags:
        re_flags |= re.IGNORECASE
    if "multiline" in flags:
        re_flags |= re.MULTILINE
    if "dotall" in flags:
        re_flags |= re.DOTALL
    
    try:
        matches = re.findall(pattern, text, re_flags)
        groups = []
        for match in re.finditer(pattern, text, re_flags):
            groups.append({
                "match": match.group(),
                "start": match.start(),
                "end": match.end(),
                "groups": match.groups() if match.groups() else None
            })
        
        return {
            "success": True,
            "match_count": len(matches),
            "matches": matches[:20],
            "details": groups[:10]
        }
    except re.error as e:
        return {"success": False, "error": f"正则表达式错误: {str(e)}"}
''',
        "enabled": True
    },
    {
        "name": "unit_converter",
        "display_name": "单位转换",
        "description": "常用单位转换，支持长度、重量、温度等",
        "code": '''def execute(arguments):
    """
    单位转换
    arguments:
        value: 数值
        from_unit: 源单位
        to_unit: 目标单位
        category: 类别 (length, weight, temperature)
    """
    value = arguments.get("value", 0)
    from_unit = arguments.get("from_unit", "").lower()
    to_unit = arguments.get("to_unit", "").lower()
    category = arguments.get("category", "length")
    
    conversions = {
        "length": {
            "m": 1, "meter": 1, "meters": 1,
            "km": 1000, "kilometer": 1000, "kilometers": 1000,
            "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
            "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
            "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
            "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
            "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
        },
        "weight": {
            "kg": 1, "kilogram": 1, "kilograms": 1,
            "g": 0.001, "gram": 0.001, "grams": 0.001,
            "mg": 0.000001, "milligram": 0.000001, "milligrams": 0.000001,
            "lb": 0.453592, "pound": 0.453592, "pounds": 0.453592,
            "oz": 0.0283495, "ounce": 0.0283495, "ounces": 0.0283495,
        }
    }
    
    try:
        if category == "temperature":
            if from_unit in ["c", "celsius"] and to_unit in ["f", "fahrenheit"]:
                result = value * 9/5 + 32
            elif from_unit in ["f", "fahrenheit"] and to_unit in ["c", "celsius"]:
                result = (value - 32) * 5/9
            elif from_unit in ["c", "celsius"] and to_unit in ["k", "kelvin"]:
                result = value + 273.15
            elif from_unit in ["k", "kelvin"] and to_unit in ["c", "celsius"]:
                result = value - 273.15
            else:
                return {"success": False, "error": "不支持的温度转换"}
        else:
            if category not in conversions:
                return {"success": False, "error": f"不支持的类别: {category}"}
            
            units = conversions[category]
            if from_unit not in units or to_unit not in units:
                return {"success": False, "error": "不支持的单位"}
            
            base_value = value * units[from_unit]
            result = base_value / units[to_unit]
        
        return {
            "success": True,
            "original": f"{value} {from_unit}",
            "converted": f"{round(result, 6)} {to_unit}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
''',
        "enabled": True
    },
    {
        "name": "hash_generator",
        "display_name": "哈希生成",
        "description": "生成字符串的哈希值，支持MD5、SHA1、SHA256等",
        "code": '''def execute(arguments):
    """
    哈希值生成
    arguments:
        text: 要哈希的文本
        algorithm: 算法 (md5, sha1, sha256, sha512)
    """
    import hashlib
    
    text = arguments.get("text", "")
    algorithm = arguments.get("algorithm", "sha256").lower()
    
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512
    }
    
    if algorithm not in algorithms:
        return {"success": False, "error": f"不支持的算法: {algorithm}"}
    
    hash_obj = algorithms[algorithm](text.encode())
    result = hash_obj.hexdigest()
    
    return {
        "success": True,
        "algorithm": algorithm,
        "hash": result,
        "length": len(result)
    }
''',
        "enabled": True
    },
    {
        "name": "ip_lookup",
        "display_name": "IP地址查询",
        "description": "查询IP地址的基本信息（模拟数据）",
        "code": '''def execute(arguments):
    """
    IP地址查询（模拟）
    arguments:
        ip: IP地址
    """
    import re
    
    ip = arguments.get("ip", "")
    
    ipv4_pattern = r"^(\\d{1,3}\\.){3}\\d{1,3}$"
    if not re.match(ipv4_pattern, ip):
        return {"success": False, "error": "无效的IP地址格式"}
    
    octets = [int(x) for x in ip.split(".")]
    if any(x > 255 for x in octets):
        return {"success": False, "error": "无效的IP地址"}
    
    is_private = (
        octets[0] == 10 or
        (octets[0] == 172 and 16 <= octets[1] <= 31) or
        (octets[0] == 192 and octets[1] == 168) or
        octets[0] == 127
    )
    
    ip_class = "私有IP" if is_private else "公网IP"
    
    return {
        "success": True,
        "ip": ip,
        "type": "IPv4",
        "class": ip_class,
        "is_private": is_private,
        "binary": ".".join(format(x, "08b") for x in octets)
    }
''',
        "enabled": True
    }
]


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[完成] 数据库表检查/创建完成")


async def init_tools():
    await create_tables()

    async with async_session_maker() as session:
        existing = await session.execute(select(ToolModel.name))
        existing_names = {row[0] for row in existing.fetchall()}

        added_count = 0
        skipped_count = 0

        for tool_data in DEFAULT_TOOLS:
            if tool_data["name"] in existing_names:
                print(f"[跳过] 工具 '{tool_data['name']}' 已存在")
                skipped_count += 1
                continue

            tool = ToolModel(
                name=tool_data["name"],
                display_name=tool_data["display_name"],
                description=tool_data["description"],
                code=tool_data["code"],
                enabled=tool_data["enabled"]
            )
            session.add(tool)
            print(
                f"[添加] 工具 '{tool_data['name']}' - {tool_data['display_name']}")
            added_count += 1

        await session.commit()

        print(f"\n完成! 添加 {added_count} 个工具, 跳过 {skipped_count} 个已存在的工具")


if __name__ == "__main__":
    print("=" * 50)
    print("AITerm 工具初始化脚本")
    print("=" * 50)
    print()
    asyncio.run(init_tools())
