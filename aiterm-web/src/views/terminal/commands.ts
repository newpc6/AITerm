export type CommandCategory = {
  name: string
  commands: CommandItem[]
}

export type CommandItem = {
  name: string
  command: string
  description: string
}

export type PlatformCommands = {
  name: string
  categories: CommandCategory[]
}

export const windowsCommands: PlatformCommands = {
  name: 'Windows (PowerShell)',
  categories: [
    {
      name: '文件操作',
      commands: [
        { name: '列出文件', command: 'Get-ChildItem', description: '列出当前目录文件' },
        { name: '切换目录', command: 'Set-Location <路径>', description: '切换到指定目录' },
        { name: '创建目录', command: 'New-Item -ItemType Directory -Name "<目录名>"', description: '创建新目录' },
        { name: '删除文件', command: 'Remove-Item <文件名>', description: '删除指定文件' },
        { name: '复制文件', command: 'Copy-Item <源> <目标>', description: '复制文件' },
        { name: '移动文件', command: 'Move-Item <源> <目标>', description: '移动文件' },
        { name: '查看文件', command: 'Get-Content <文件名>', description: '查看文件内容' },
        { name: '当前路径', command: 'Get-Location', description: '显示当前工作目录' },
      ],
    },
    {
      name: '进程管理',
      commands: [
        { name: '查看进程', command: 'Get-Process', description: '列出所有进程' },
        { name: '查找进程', command: 'Get-Process -Name "<进程名>"', description: '按名称查找进程' },
        { name: '停止进程', command: 'Stop-Process -Name "<进程名>"', description: '停止指定进程' },
        { name: '停止进程ID', command: 'Stop-Process -Id <PID>', description: '按进程ID停止' },
      ],
    },
    {
      name: '网络相关',
      commands: [
        { name: 'IP配置', command: 'Get-NetIPConfiguration', description: '查看网络配置' },
        { name: '测试连接', command: 'Test-Connection <主机名>', description: '测试网络连接' },
        { name: '端口查看', command: 'Get-NetTCPConnection', description: '查看TCP连接' },
        { name: 'DNS解析', command: 'Resolve-DnsName <域名>', description: '解析域名DNS' },
      ],
    },
    {
      name: '系统信息',
      commands: [
        { name: '系统信息', command: 'Get-ComputerInfo', description: '查看系统信息' },
        { name: '磁盘空间', command: 'Get-PSDrive -PSProvider FileSystem', description: '查看磁盘空间' },
        { name: '服务列表', command: 'Get-Service', description: '列出所有服务' },
        { name: '环境变量', command: 'Get-ChildItem Env:', description: '查看环境变量' },
        { name: '当前时间', command: 'Get-Date', description: '显示当前日期时间' },
        { name: '系统版本', command: '[System.Environment]::OSVersion', description: '查看系统版本' },
      ],
    },
    {
      name: '服务管理',
      commands: [
        { name: '启动服务', command: 'Start-Service -Name "<服务名>"', description: '启动服务' },
        { name: '停止服务', command: 'Stop-Service -Name "<服务名>"', description: '停止服务' },
        { name: '重启服务', command: 'Restart-Service -Name "<服务名>"', description: '重启服务' },
        { name: '服务状态', command: 'Get-Service -Name "<服务名>"', description: '查看服务状态' },
      ],
    },
  ],
}

export const linuxCommands: PlatformCommands = {
  name: 'Linux / macOS',
  categories: [
    {
      name: '文件操作',
      commands: [
        { name: '列出文件', command: 'ls -la', description: '列出所有文件（含隐藏）' },
        { name: '切换目录', command: 'cd <路径>', description: '切换到指定目录' },
        { name: '创建目录', command: 'mkdir -p <目录名>', description: '创建目录（含父目录）' },
        { name: '删除文件', command: 'rm <文件名>', description: '删除文件' },
        { name: '删除目录', command: 'rm -rf <目录名>', description: '递归删除目录' },
        { name: '复制文件', command: 'cp -r <源> <目标>', description: '递归复制' },
        { name: '移动文件', command: 'mv <源> <目标>', description: '移动或重命名' },
        { name: '查看文件', command: 'cat <文件名>', description: '查看文件内容' },
        { name: '当前路径', command: 'pwd', description: '显示当前工作目录' },
        { name: '查找文件', command: 'find . -name "<文件名>"', description: '查找文件' },
      ],
    },
    {
      name: '进程管理',
      commands: [
        { name: '查看进程', command: 'ps aux', description: '列出所有进程' },
        { name: '查找进程', command: 'ps aux | grep <进程名>', description: '按名称查找进程' },
        { name: '停止进程', command: 'killall <进程名>', description: '停止指定进程' },
        { name: '停止进程ID', command: 'kill <PID>', description: '按进程ID停止' },
        { name: '强制停止', command: 'kill -9 <PID>', description: '强制停止进程' },
        { name: '进程树', command: 'pstree', description: '显示进程树' },
      ],
    },
    {
      name: '网络相关',
      commands: [
        { name: 'IP配置', command: 'ifconfig', description: '查看网络配置' },
        { name: '测试连接', command: 'ping -c 4 <主机名>', description: '测试网络连接' },
        { name: '端口查看', command: 'netstat -tlnp', description: '查看监听端口' },
        { name: 'DNS解析', command: 'nslookup <域名>', description: '解析域名DNS' },
        { name: '下载文件', command: 'curl -O <URL>', description: '下载文件' },
        { name: '路由表', command: 'route -n', description: '查看路由表' },
      ],
    },
    {
      name: '系统信息',
      commands: [
        { name: '磁盘空间', command: 'df -h', description: '查看磁盘空间' },
        { name: '内存使用', command: 'free -h', description: '查看内存使用' },
        { name: '系统负载', command: 'top -n 1', description: '查看系统负载' },
        { name: '系统版本', command: 'uname -a', description: '查看系统版本' },
        { name: '当前时间', command: 'date', description: '显示当前日期时间' },
        { name: '环境变量', command: 'env', description: '查看环境变量' },
      ],
    },
    {
      name: '服务管理',
      commands: [
        { name: '启动服务', command: 'systemctl start <服务名>', description: '启动服务' },
        { name: '停止服务', command: 'systemctl stop <服务名>', description: '停止服务' },
        { name: '重启服务', command: 'systemctl restart <服务名>', description: '重启服务' },
        { name: '服务状态', command: 'systemctl status <服务名>', description: '查看服务状态' },
        { name: '开机启动', command: 'systemctl enable <服务名>', description: '设置开机启动' },
        { name: '禁用启动', command: 'systemctl disable <服务名>', description: '禁用开机启动' },
      ],
    },
    {
      name: '权限管理',
      commands: [
        { name: '修改权限', command: 'chmod 755 <文件名>', description: '修改文件权限' },
        { name: '修改所有者', command: 'chown <用户>:<组> <文件名>', description: '修改文件所有者' },
        { name: '切换用户', command: 'su - <用户名>', description: '切换用户' },
        { name: 'sudo执行', command: 'sudo <命令>', description: '以管理员权限执行' },
      ],
    },
    {
      name: '压缩解压',
      commands: [
        { name: '压缩tar', command: 'tar -czvf <文件名>.tar.gz <目录>', description: '压缩目录' },
        { name: '解压tar', command: 'tar -xzvf <文件名>.tar.gz', description: '解压tar.gz' },
        { name: '压缩zip', command: 'zip -r <文件名>.zip <目录>', description: '压缩为zip' },
        { name: '解压zip', command: 'unzip <文件名>.zip', description: '解压zip' },
      ],
    },
  ],
}

export const macCommands: PlatformCommands = {
  name: 'macOS 专用',
  categories: [
    {
      name: '系统操作',
      commands: [
        { name: 'Homebrew安装', command: 'brew install <包名>', description: '使用Homebrew安装软件' },
        { name: 'Homebrew搜索', command: 'brew search <包名>', description: '搜索软件包' },
        { name: 'Homebrew更新', command: 'brew update && brew upgrade', description: '更新Homebrew和软件' },
        { name: '查看应用', command: 'ls /Applications', description: '列出已安装应用' },
        { name: '打开应用', command: 'open -a "<应用名>"', description: '打开应用程序' },
      ],
    },
    {
      name: '磁盘管理',
      commands: [
        { name: '磁盘信息', command: 'diskutil list', description: '列出所有磁盘' },
        { name: '磁盘空间', command: 'df -h', description: '查看磁盘空间' },
        { name: '卸载磁盘', command: 'diskutil unmount <磁盘>', description: '卸载磁盘' },
      ],
    },
    {
      name: '系统信息',
      commands: [
        { name: '系统概览', command: 'system_profiler SPSoftwareDataType', description: '查看系统信息' },
        { name: '硬件信息', command: 'system_profiler SPHardwareDataType', description: '查看硬件信息' },
        { name: '电池状态', command: 'pmset -g batt', description: '查看电池状态' },
        { name: 'CPU信息', command: 'sysctl -n machdep.cpu.brand_string', description: '查看CPU型号' },
      ],
    },
  ],
}

export const commonCommands: CommandCategory = {
  name: '通用命令',
  commands: [
    { name: '查看帮助', command: '<命令> --help', description: '查看命令帮助信息' },
    { name: '清屏', command: 'clear', description: '清空终端屏幕' },
    { name: '查看历史', command: 'history', description: '查看命令历史' },
    { name: '输出文本', command: 'echo "<文本>"', description: '输出文本内容' },
    { name: '查看时间', command: 'date', description: '显示当前时间' },
    { name: '计算器', command: 'expr 1 + 1', description: '简单计算' },
  ],
}

export function getAllCommands() {
  return {
    common: commonCommands,
    windows: windowsCommands,
    linux: linuxCommands,
    mac: macCommands,
  }
}
