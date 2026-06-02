# 钟文清 — 个人作品集

> 数据工程师 × 创意开发者 · 深圳 · Apple 玻璃质感单页作品集

一个精心设计的个人作品集前端页面，展示项目作品、技术栈、工作经历。

## 设计理念

- **编辑式排版**: 非对称布局，70/30 分割，戏剧化的空间节奏
- **暗夜蓝紫色调**: OKLCH 色彩空间，零纯黑零纯白
- **日系字体组合**: Zen Old Mincho + Zen Kaku Gothic New + M PLUS Rounded 1c
- **Apple 玻璃质感**: `backdrop-filter` 毛玻璃 + 噪点纹理叠加层
- **暗色/亮色双主题**: localStorage 记忆，一键切换
- **零依赖**: 单文件 HTML + CSS + 原生 JS

## 快速开始

直接用浏览器打开 `index.html`，或挂到任意静态服务器：

```bash
# Python 简单服务器
python -m http.server 8080
```

## 功能分区

| 区域 | 内容 |
|------|------|
| Hero | 非对称英雄区，带浮动技能标签动画 |
| About | 个人简介 + 数据统计卡片（70/30 分栏） |
| Skills | 四组技能标签云，核心技能高亮 |
| Projects | 四个精选项目，交替左右布局 |
| Experience | 垂直时间线 |
| Contact | 联系信息卡片网格 |

## 部署

单文件可直接部署到任何静态服务器（Nginx、GitHub Pages、Vercel 等）。

## License

MIT
