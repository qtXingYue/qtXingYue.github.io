import subprocess, sys, time

host = "119.29.229.120"
password = "123456@nM"

deploy_cmds = r"""
apt update && apt install -y nginx git && mkdir -p /var/www/portfolio && git clone https://github.com/qtXingYue/anime-blog.git /var/www/portfolio && chown -R www-data:www-data /var/www/portfolio && cat > /etc/nginx/sites-available/portfolio << 'NGXEOF'
server {
    listen 80;
    server_name www.qtxingyue.me;
    root /var/www/portfolio;
    index index.html;
    location / { try_files $uri $uri/ =404; }
    gzip on;
    gzip_types text/plain text/css application/javascript text/xml text/javascript;
}
NGXEOF
ln -sf /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled/ && rm -f /etc/nginx/sites-enabled/default && nginx -t && systemctl reload nginx && echo "DONE"
"""

print("Connecting to server...")
proc = subprocess.Popen(
    ["ssh", "-o", "StrictHostKeyChecking=no", f"root@{host}", "bash -s"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, bufsize=1
)

# Send password
proc.stdin.write(password + "\n")
proc.stdin.flush()
time.sleep(2)

# Send deploy commands
proc.stdin.write(deploy_cmds + "\n")
proc.stdin.close()

# Read output
output, _ = proc.communicate(timeout=120)
print(output)

if proc.returncode == 0:
    print("\n✅ 部署成功！请去 Namecheap DNS 添加 A 记录: www → 119.29.229.120")
else:
    print(f"\n❌ 失败 (code {proc.returncode})")
