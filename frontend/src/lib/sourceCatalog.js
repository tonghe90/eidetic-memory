export const SOURCE_CATALOG = {
  gmail: {
    label: "Gmail",
    icon: "📧",
    authGuide: "通过 Google OAuth 授权只读邮件访问。点击授权后会打开 Google 登录页面。",
  },
  googledocs: {
    label: "Google Docs",
    icon: "📝",
    authGuide: "通过 Google OAuth 授权只读 Google Docs 访问。同步后会抓取文档正文与原始链接。",
  },
  chrome: {
    label: "Google Chrome",
    icon: "🌐",
    authGuide: "需要在系统设置 → 隐私与安全 → 完全磁盘访问中授权本应用。",
  },
  chatgpt: {
    label: "ChatGPT",
    icon: "💬",
    authGuide: "点击「打开 ChatGPT」后，浏览器扩展会自动检测并同步对话历史。",
  },
  claude: {
    label: "Claude.ai",
    icon: "🤖",
    authGuide: "点击「打开 Claude.ai」后，浏览器扩展会自动检测并同步对话历史。",
  },
};

export const SOURCE_ORDER = ["gmail", "googledocs", "chrome", "chatgpt", "claude"];

export function getSourceLabel(source) {
  return SOURCE_CATALOG[source]?.label ?? source;
}

export function getSourceIcon(source) {
  return SOURCE_CATALOG[source]?.icon ?? "📄";
}

export function getAuthGuide(source) {
  return SOURCE_CATALOG[source]?.authGuide ?? "";
}

export function getSourceFromUrl(url) {
  if (!url) return null;
  if (url.includes("mail.google")) return "gmail";
  if (url.includes("docs.google.com")) return "googledocs";
  if (url.includes("chatgpt.com")) return "chatgpt";
  if (url.includes("claude.ai")) return "claude";
  if (url.startsWith("http")) return "chrome";
  return null;
}
