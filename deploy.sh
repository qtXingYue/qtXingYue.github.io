#!/bin/bash
# 一键部署脚本 - 适用于 Ubuntu 22.04
# 域名: www.qtxingyue.me

set -e

SERVER_IP="119.29.229.120"
DOMAIN="www.qtxingyue.me"
REPO="https://github.com/qtXingYue/anime-blog.git"
WEB_ROOT="/var/www/portfolio"

echo "🚀 开始部署..."

# 1. 更新系统
apt update && apt upgrade -y

# 2. 安装 Nginx 和 Git
apt install -y nginx git

# 3. 克隆/更新仓库
if [ -d "$WEB_ROOT/.git" ]; then
    cd $WEB_ROOT && git pull
else
    rm -rf $WEB_ROOT
    git clone $REPO $WEB_ROOT
fi

# 4. 设置权限
chown -R www-data:www-data $WEB_ROOT
chmod -R 755 $WEB_ROOT

# 5. 配置 Nginx
cat > /etc/nginx/sites-available/portfolio << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name www.qtxingyue.me;
    root /var/www/portfolio;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # 开启 gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # 缓存静态资源
    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# 6. 启用站点
ln -sf /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 7. 测试并重载 Nginx
nginx -t && systemctl reload nginx

# 8. 确保防火墙允许 80/443
ufw allow 80/tcp 2>/dev/null || true
ufw allow 443/tcp 2>/dev/null || true

echo ""
echo "✅ 部署完成！"
echo ""
echo "下一步："
echo "1. 登录 Namecheap DNS 管理"
echo "2. 添加 CNAME 记录："
echo "   主机: www"
echo "   值: $SERVER_IP (A 记录) 或 119.29.229.120"
echo ""
echo "访问地址: http://www.qtxingyue.me"
