# FOLIO 折页

多语种原版书推荐网站。杂志式荐读，不提供购买。

本机没有可用的 Node.js，因此没有使用 Next.js，而是用 FastAPI + Jinja2 + SQLite 做成可公网部署的服务端渲染站点。每种语言有独立 URL，评论和评分写入 SQLite。

## 本地启动

```bash
cd "/Users/zhangfanfan/Desktop/inspiration/书籍推荐"
python3 -m pip install -r requirements.txt
python3 scripts/import_xlsx.py
python3 -m folio.seed
python3 run.py
```

浏览器打开 `http://127.0.0.1:8000`。

## 测试

```bash
python3 -m pytest tests -q
```

## 生产构建 / 运行

Python 站点没有前端打包步骤。发布前请运行：

```bash
python3 -m compileall folio scripts
python3 -m pytest tests -q
export FOLIO_SECRET_KEY='长随机串'
export FOLIO_ADMIN_KEY='管理员密钥'
export FOLIO_DB='data/folio.db'
python3 run.py
```

构建镜像：

```bash
docker build -t folio .
docker run -p 8000:8000 -e FOLIO_SECRET_KEY=... -e FOLIO_ADMIN_KEY=... folio
```

部署到 Render / Fly / Railway：本仓库根目录已有 `Dockerfile` 和 `render.yaml`。在 Render 控制台选择 **New → Blueprint**，连接本 GitHub 仓库即可；密钥 `FOLIO_SECRET_KEY` / `FOLIO_ADMIN_KEY` 会自动生成，SQLite 写在 1GB 磁盘 `/app/data`。

## 导入下一批 XLSX

把表格放入对应语言文件夹，或 `incoming/`，然后：

```bash
python3 scripts/import_xlsx.py          # 或加 --dry-run
python3 -m folio.seed
```

脚本按 ISBN（去连字符）去重；无 ISBN 时按语言+书名+作者去重。购书渠道列不会进入网站。

## 新增一期推荐

1. 在 `folio/config.py` 修改 `ISSUE_YEAR` / `ISSUE_MONTH`。
2. 在 `folio/featured.py` 追加该期八本/语言的核验文案，或新增 issue 记录后把 `is_featured` 指到新 `issues.id`。
3. 运行 `python3 -m folio.seed`。

不要虚构往期。没有内容时，「往期推荐」会显示空状态。

## 管理员评论审核

请求头 `x-folio-admin: $FOLIO_ADMIN_KEY`，调用：

`POST /api/admin/comments/{id}/moderate`  JSON `{"action":"hide"|"restore"|"delete"}`

## 重要路径

- `folio/main.py` 网站与 API
- `folio/models.py` 数据模型
- `folio/featured.py` 本期 48 本编辑文案
- `scripts/import_xlsx.py` 表格导入
- `data/cleaned-books.json` 清洗后的统一书目
- `templates/` 页面
- `reference/folio.html` 原始 FOLIO 参考页
