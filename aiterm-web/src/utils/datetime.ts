export function formatDateTime(utcString: string | undefined | null): string {
  if (!utcString) {
    return '-'
  }

  try {
    const date = new Date(utcString)
    if (Number.isNaN(date.getTime())) {
      return utcString
    }

    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')

    return `${year}-${month}-${day} ${hours}:${minutes}`
  } catch {
    return utcString
  }
}

export function formatTime(utcString: string | undefined | null): string {
  if (!utcString) {
    return '-'
  }

  try {
    const date = new Date(utcString)
    if (Number.isNaN(date.getTime())) {
      return utcString
    }

    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')

    return `${hours}:${minutes}:${seconds}`
  } catch {
    return utcString
  }
}

export function formatRelativeTime(utcString: string | undefined | null): string {
  if (!utcString) {
    return '-'
  }

  try {
    const date = new Date(utcString)
    if (Number.isNaN(date.getTime())) {
      return utcString
    }

    const now = new Date()
    const diff = now.getTime() - date.getTime()

    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (seconds < 60) {
      return '刚刚'
    } else if (minutes < 60) {
      return `${minutes} 分钟前`
    } else if (hours < 24) {
      return `${hours} 小时前`
    } else if (days < 7) {
      return `${days} 天前`
    } else {
      return formatDateTime(utcString)
    }
  } catch {
    return utcString
  }
}
