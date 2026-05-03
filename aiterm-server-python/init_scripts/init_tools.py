"""
工具初始化脚本
运行此脚本可以导入预设的工具到数据库中

使用方法:
    cd aiterm-server-python
    python scripts/init_tools.py
"""

from app.db import async_session_maker, engine
from app.db.base import Base
from app.db.tool import ToolModel
from sqlalchemy import select
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
        "enabled": True,
        "sandbox_only": False
    },
    {
        "name": "read_file",
        "display_name": "读取文件",
        "description": "读取指定路径的文件内容，支持文本文件",
        "code": '''def execute(arguments):
    """
    读取文件内容
    arguments:
        path: 文件路径
        encoding: 编码格式，默认utf-8
        lines: 可选，读取指定行数
    """
    import os
    
    path = arguments.get("path", "")
    encoding = arguments.get("encoding", "utf-8")
    max_lines = arguments.get("lines", None)
    
    if not path:
        return {"success": False, "error": "请提供文件路径"}
    
    if not os.path.exists(path):
        return {"success": False, "error": f"文件不存在: {path}"}
    
    if not os.path.isfile(path):
        return {"success": False, "error": f"路径不是文件: {path}"}
    
    try:
        with open(path, "r", encoding=encoding) as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
                content = "".join(lines)
            else:
                content = f.read()
        
        file_size = os.path.getsize(path)
        
        return {
            "success": True,
            "path": path,
            "content": content,
            "size": file_size,
            "lines": content.count("\\n") + 1
        }
    except Exception as e:
        return {"success": False, "error": f"读取文件失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "write_file",
        "display_name": "写入文件",
        "description": "将内容写入指定路径的文件，支持创建和覆盖",
        "code": '''def execute(arguments):
    """
    写入文件
    arguments:
        path: 文件路径
        content: 要写入的内容
        mode: 写入模式，write(覆盖)或append(追加)，默认write
        encoding: 编码格式，默认utf-8
    """
    import os
    
    path = arguments.get("path", "")
    content = arguments.get("content", "")
    mode = arguments.get("mode", "write")
    encoding = arguments.get("encoding", "utf-8")
    
    if not path:
        return {"success": False, "error": "请提供文件路径"}
    
    try:
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        
        write_mode = "a" if mode == "append" else "w"
        with open(path, write_mode, encoding=encoding) as f:
            f.write(content)
        
        file_size = os.path.getsize(path)
        
        return {
            "success": True,
            "path": path,
            "size": file_size,
            "mode": mode
        }
    except Exception as e:
        return {"success": False, "error": f"写入文件失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "list_directory",
        "display_name": "列出目录",
        "description": "列出指定目录下的文件和子目录",
        "code": '''def execute(arguments):
    """
    列出目录内容
    arguments:
        path: 目录路径
        pattern: 可选，文件匹配模式，如 *.txt
        show_hidden: 是否显示隐藏文件，默认False
    """
    import os
    import fnmatch
    
    path = arguments.get("path", "")
    pattern = arguments.get("pattern", "*")
    show_hidden = arguments.get("show_hidden", False)
    
    if not path:
        return {"success": False, "error": "请提供目录路径"}
    
    if not os.path.exists(path):
        return {"success": False, "error": f"目录不存在: {path}"}
    
    if not os.path.isdir(path):
        return {"success": False, "error": f"路径不是目录: {path}"}
    
    try:
        items = []
        for item in os.listdir(path):
            if not show_hidden and item.startswith("."):
                continue
            if not fnmatch.fnmatch(item, pattern):
                continue
            
            item_path = os.path.join(path, item)
            is_dir = os.path.isdir(item_path)
            size = 0 if is_dir else os.path.getsize(item_path)
            mtime = os.path.getmtime(item_path)
            
            items.append({
                "name": item,
                "type": "directory" if is_dir else "file",
                "size": size,
                "modified": mtime
            })
        
        items.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
        
        return {
            "success": True,
            "path": path,
            "items": items,
            "count": len(items)
        }
    except Exception as e:
        return {"success": False, "error": f"列出目录失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "delete_file",
        "display_name": "删除文件",
        "description": "删除指定的文件",
        "code": '''def execute(arguments):
    """
    删除文件
    arguments:
        path: 文件路径
    """
    import os
    import shutil
    
    path = arguments.get("path", "")
    
    if not path:
        return {"success": False, "error": "请提供文件路径"}
    
    if not os.path.exists(path):
        return {"success": False, "error": f"文件不存在: {path}"}
    
    try:
        if os.path.isfile(path):
            os.remove(path)
            return {"success": True, "path": path, "type": "file", "action": "deleted"}
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return {"success": True, "path": path, "type": "directory", "action": "deleted"}
        else:
            return {"success": False, "error": "未知的文件类型"}
    except Exception as e:
        return {"success": False, "error": f"删除失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "copy_file",
        "display_name": "复制文件",
        "description": "复制文件到指定路径",
        "code": '''def execute(arguments):
    """
    复制文件
    arguments:
        source: 源文件路径
        destination: 目标路径
    """
    import os
    import shutil
    
    source = arguments.get("source", "")
    destination = arguments.get("destination", "")
    
    if not source or not destination:
        return {"success": False, "error": "请提供源路径和目标路径"}
    
    if not os.path.exists(source):
        return {"success": False, "error": f"源文件不存在: {source}"}
    
    try:
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        
        return {
            "success": True,
            "source": source,
            "destination": destination,
            "size": os.path.getsize(destination) if os.path.isfile(destination) else None
        }
    except Exception as e:
        return {"success": False, "error": f"复制失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "move_file",
        "display_name": "移动文件",
        "description": "移动或重命名文件",
        "code": '''def execute(arguments):
    """
    移动文件
    arguments:
        source: 源文件路径
        destination: 目标路径
    """
    import os
    import shutil
    
    source = arguments.get("source", "")
    destination = arguments.get("destination", "")
    
    if not source or not destination:
        return {"success": False, "error": "请提供源路径和目标路径"}
    
    if not os.path.exists(source):
        return {"success": False, "error": f"源文件不存在: {source}"}
    
    try:
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        
        shutil.move(source, destination)
        
        return {
            "success": True,
            "source": source,
            "destination": destination
        }
    except Exception as e:
        return {"success": False, "error": f"移动失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "http_request",
        "display_name": "HTTP请求",
        "description": "发送HTTP请求，支持GET、POST等方法",
        "code": '''def execute(arguments):
    """
    发送HTTP请求
    arguments:
        url: 请求URL
        method: 请求方法，默认GET
        headers: 请求头，字典格式
        params: URL参数，字典格式
        data: 请求体数据
        json_data: JSON格式的请求体
        timeout: 超时时间(秒)，默认30
    """
    import urllib.request
    import urllib.parse
    import json
    
    url = arguments.get("url", "")
    method = arguments.get("method", "GET").upper()
    headers = arguments.get("headers", {})
    params = arguments.get("params", {})
    data = arguments.get("data")
    json_data = arguments.get("json_data")
    timeout = arguments.get("timeout", 30)
    
    if not url:
        return {"success": False, "error": "请提供请求URL"}
    
    try:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        
        request_data = None
        if json_data:
            request_data = json.dumps(json_data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif data:
            request_data = data.encode("utf-8") if isinstance(data, str) else data
        
        req = urllib.request.Request(url, data=request_data, headers=headers, method=method)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            response_headers = dict(response.headers)
            status_code = response.status
            
            try:
                response_json = json.loads(response_body)
            except:
                response_json = None
        
        return {
            "success": True,
            "status_code": status_code,
            "headers": response_headers,
            "body": response_body,
            "json": response_json
        }
    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP错误: {e.code} {e.reason}",
            "status_code": e.code
        }
    except urllib.error.URLError as e:
        return {"success": False, "error": f"URL错误: {str(e.reason)}"}
    except Exception as e:
        return {"success": False, "error": f"请求失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": False
    },
    {
        "name": "download_file",
        "display_name": "下载文件",
        "description": "从URL下载文件到本地",
        "code": '''def execute(arguments):
    """
    下载文件
    arguments:
        url: 文件URL
        save_path: 保存路径
        filename: 可选，文件名，不指定则从URL提取
        timeout: 超时时间(秒)，默认60
    """
    import os
    import urllib.request
    import urllib.parse
    
    url = arguments.get("url", "")
    save_path = arguments.get("save_path", "")
    filename = arguments.get("filename", "")
    timeout = arguments.get("timeout", 60)
    
    if not url:
        return {"success": False, "error": "请提供文件URL"}
    
    if not save_path:
        return {"success": False, "error": "请提供保存路径"}
    
    try:
        if not filename:
            parsed = urllib.parse.urlparse(url)
            filename = os.path.basename(parsed.path) or "downloaded_file"
        
        full_path = os.path.join(save_path, filename)
        
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
        
        urllib.request.urlretrieve(url, full_path)
        
        file_size = os.path.getsize(full_path)
        
        return {
            "success": True,
            "url": url,
            "path": full_path,
            "filename": filename,
            "size": file_size
        }
    except Exception as e:
        return {"success": False, "error": f"下载失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "create_directory",
        "display_name": "创建目录",
        "description": "创建目录，支持多级创建",
        "code": '''def execute(arguments):
    """
    创建目录
    arguments:
        path: 目录路径
    """
    import os
    
    path = arguments.get("path", "")
    
    if not path:
        return {"success": False, "error": "请提供目录路径"}
    
    try:
        os.makedirs(path, exist_ok=True)
        
        return {
            "success": True,
            "path": path,
            "created": True
        }
    except Exception as e:
        return {"success": False, "error": f"创建目录失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "get_file_info",
        "display_name": "获取文件信息",
        "description": "获取文件的详细信息，包括大小、修改时间等",
        "code": '''def execute(arguments):
    """
    获取文件信息
    arguments:
        path: 文件路径
    """
    import os
    from datetime import datetime
    
    path = arguments.get("path", "")
    
    if not path:
        return {"success": False, "error": "请提供文件路径"}
    
    if not os.path.exists(path):
        return {"success": False, "error": f"文件不存在: {path}"}
    
    try:
        stat = os.stat(path)
        
        return {
            "success": True,
            "path": path,
            "type": "directory" if os.path.isdir(path) else "file",
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            "is_readable": os.access(path, os.R_OK),
            "is_writable": os.access(path, os.W_OK),
            "is_executable": os.access(path, os.X_OK)
        }
    except Exception as e:
        return {"success": False, "error": f"获取文件信息失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
    },
    {
        "name": "search_files",
        "display_name": "搜索文件",
        "description": "在目录中搜索匹配的文件",
        "code": '''def execute(arguments):
    """
    搜索文件
    arguments:
        path: 搜索目录
        pattern: 文件名模式，支持通配符
        recursive: 是否递归搜索，默认True
        max_results: 最大结果数，默认100
    """
    import os
    import fnmatch
    
    path = arguments.get("path", "")
    pattern = arguments.get("pattern", "*")
    recursive = arguments.get("recursive", True)
    max_results = arguments.get("max_results", 100)
    
    if not path:
        return {"success": False, "error": "请提供搜索目录"}
    
    if not os.path.exists(path):
        return {"success": False, "error": f"目录不存在: {path}"}
    
    try:
        matches = []
        
        if recursive:
            for root, dirs, files in os.walk(path):
                for name in files + dirs:
                    if fnmatch.fnmatch(name.lower(), pattern.lower()):
                        matches.append(os.path.join(root, name))
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break
        else:
            for name in os.listdir(path):
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    matches.append(os.path.join(path, name))
                    if len(matches) >= max_results:
                        break
        
        return {
            "success": True,
            "path": path,
            "pattern": pattern,
            "matches": matches,
            "count": len(matches)
        }
    except Exception as e:
        return {"success": False, "error": f"搜索失败: {str(e)}"}
''',
        "enabled": True,
        "sandbox_only": True
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
                enabled=tool_data["enabled"],
                sandbox_only=tool_data.get("sandbox_only", False)
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
